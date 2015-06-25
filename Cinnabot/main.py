#! /usr/bin/python
# -*- coding=utf-8 -*-

import optparse
import os
import ConfigParser
import irc.client
import logging
import re
import sys
import imp
import subprocess

DEBUG_LEVELS = {
   0: logging.FATAL,
   1: logging.ERROR,
   2: logging.WARNING,
   3: logging.INFO,
   4: logging.DEBUG
}

ADMIN_COMMANDS_RE = {
    "^\\ *quit\\ *$": "quit",
    "^\\ *restart\\ *$": "restart",
    "^\\ *update\\ *$": "update",
    "^\\ *reload\ config\\ *$": "reload_config",
    "^\\ *join\\ channel(\\ +#+[a-zA-Z0-9\\-\\_]+)\\ *$": "join_channel",
    "^\\ *join(\\ +#+[a-zA-Z0-9\\-\\_]+)\\ *$": "join_channel",
    "^\\ *leave\\ channel(\\ +#+[a-zA-Z0-9\\-\\_]+)?\\ *$": "leave_channel",
    "^\\ *leave(\\ +#+[a-zA-Z0-9\\-\\_]+)?\\ *$": "leave_channel",
    "^\\ *save channels\\ *$": "save_channels",
    "^\\ *load plugin(\\ +[a-zA-Z]+)\\ *$": "load_plugin",
    "^\\ *unload plugin(\\ +[a-zA-Z]+)\\ *$": "unload_plugin"
}

class CustomLogHandler(logging.StreamHandler):
    def __init__(self, bot):
        logging.StreamHandler.__init__(self)
        
        self._bot = bot
        
        formatter = logging.Formatter(logging.BASIC_FORMAT, None)
        self.setFormatter(formatter)
    
    def handle(self, record):
        logging.StreamHandler.handle(self, record)
        
        if record.levelno >= logging.WARN:
            self._bot.send_warn_privmsg(self.format(record))

class Cinnabot(object):
    def __init__(self):
        self._parse_cli_options()
        self._load_config()
        self._init_logger()
        
        self._admin_commands = {}
        self._semi_admin_commands = {}
        for regexp in ADMIN_COMMANDS_RE:
            self._admin_commands[re.compile(regexp)] = getattr(self, "_admin_" + ADMIN_COMMANDS_RE[regexp])
            if ADMIN_COMMANDS_RE[regexp] in self._allowed_semi_admin_commands:
                self._semi_admin_commands[re.compile(regexp)] = self._admin_commands[re.compile(regexp)]
        
        self._is_saving_channels = False
        
        self._plugins = {}
        
        self._identify_user_queue = {}
        self._whoisuser_queue = {}
        self._nick_to_mask_map = {}
        self._nick_to_username_map = {}
        self._operators = {}
    
    def _parse_cli_options(self):
        optparser = optparse.OptionParser()
        optparser.add_option('-c', '--config-file', dest = "config_file", default = os.path.join(os.getenv("HOME"), ".config", "cinnabot", "cinnabot.conf"))
        optparser.add_option("-d", "--debug-level", dest = "debug_level", type = "int", default = 2)
        self.cli_options = optparser.parse_args()[0]
        
        self.cli_options.config_file = os.path.realpath(self.cli_options.config_file)
    
    def _init_logger(self):
        logging.getLogger().setLevel(DEBUG_LEVELS[self.cli_options.debug_level])
        
        custom_handler = CustomLogHandler(self)
        logging.getLogger().addHandler(custom_handler)
        
        file_handler = logging.FileHandler(os.path.join(os.getenv("HOME"), ".config", "cinnabot", "cinnabot.log"))
        file_handler.setLevel(logging.WARN)
        formatter = logging.Formatter("%(asctime)s:" + logging.BASIC_FORMAT, None)
        file_handler.setFormatter(formatter)
        logging.getLogger().addHandler(file_handler)
    
    def _load_config(self):
        self.config = ConfigParser.RawConfigParser()
        self.config.read(self.cli_options.config_file)
        
        self._admin_usernames = []
        for key in self.config.options("Admin"):
            if key.startswith("admin_username"):
                self._admin_usernames.append(self.config.get("Admin", key))
        
        if self.config.has_option("Admin", "allowed_semi_admin_commands"):
            self._allowed_semi_admin_commands = self.config.get("Admin", "allowed_semi_admin_commands").split(",")
        else:
            self._allowed_semi_admin_commands = []
    
    def send_warn_privmsg(self, msg):
        if self.config.has_option("General", "send_log_to"):
            self._irc_server_connection.privmsg(self.config.get("General", "send_log_to"), u"\x0305\x02" + msg + u"\x0f")
    
    def _save_config(self):
        f = open(self.cli_options.config_file, "w")
        self.config.write(f)
        f.close()
    
    def _on_irc_welcome(self, server_connection, event):
        logging.info("_on_irc_welcome")
        self._irc_server_connection.privmsg("NickServ", "identify %s %s" % (self.config.get("General", "username"), self.config.get("General", "password")))
        self._irc_server_connection.mode(self._irc_server_connection.get_nickname(), "+B")
    
    def _on_irc_login(self, server_connection, event):
        logging.info("_on_irc_login:" + str(event.arguments))
        for channel in self.config.get("General", "join_channels").split(","):
            self._irc_server_connection.join(channel)
        
        self._load_plugins()
        self._check_operators()
    
    def _unload_plugin(self, plugin_name):
        logging.info("_unload_plugin:" + plugin_name)
        
        self._plugins[plugin_name].unload()
        del self._plugins[plugin_name]
            
    def _unload_plugins(self):
        logging.info("_unload_plugins")
        
        for i in self._plugins.keys():
            self._unload_plugin(i)
    
    def _load_plugin(self, plugin_name):
        logging.info("_load_plugin:" + plugin_name)
        
        if plugin_name in self._plugins:
            self._unload_plugin(plugin_name)
        
        plugin_file = os.path.join(os.path.split(__file__)[0], "plugins", plugin_name + ".py")
        if os.path.exists(plugin_file):
            try:
                f = open(plugin_file)
                m = imp.load_module(plugin_name, f, plugin_file, ('.py', 'r', imp.PY_SOURCE))
                plugin_class = getattr(m, plugin_name + "Plugin")
                plugin = plugin_class(self, plugin_name)
                self._plugins[plugin_name] = plugin
                if hasattr(m, "USE_DB") and m.USE_DB:
                    plugin.init_db(m.DB_UPGRADES)
            except:
                logging.warn("Failed to load plugin %s : %s" % (plugin_name, str(sys.exc_info())))
        else:
            logging.warn("Missing plugin : " + plugin_file)
            
    def _load_plugins(self):
        logging.info("_load_plugins")
        
        self._unload_plugins()
        
        for section in self.config.sections():
            if section.startswith("Plugin/"):
                if self.config.getboolean(section, "enabled"):
                    plugin_name = section[7:]
                    self._load_plugin(plugin_name)
    
    def _is_admin(self, username):
        return username != "" and username in self._admin_usernames
    
    def _is_semi_admin(self, source):
        if not self.config.has_option("Admin", "semi_admin_channel_ops"):
            return False
            
        nickname = source.split("!")[0]
        
        if not nickname in self._nick_to_username_map:
            return False
        
        for c in self.config.get("Admin", "semi_admin_channel_ops").split(","):
            if nickname in self._operators.setdefault(c, []):
                return True

        return False
    
    def _identify_user(self, source, callback, *args):
        nickname = source.split("!")[0]
        if not nickname in self._nick_to_mask_map or self._nick_to_mask_map[nickname] != source:
            if nickname in self._nick_to_mask_map:
                del self._nick_to_mask_map[nickname]
            if nickname in self._nick_to_username_map:
                del self._nick_to_username_map[nickname]
        
        if nickname in self._nick_to_username_map:
            callback(self._nick_to_username_map[nickname], *args)
        else:
            self._nick_to_mask_map[nickname] = source
            if not nickname in self._identify_user_queue:
                self._identify_user_queue[nickname] = []
            self._identify_user_queue[nickname].append((callback, args))
            self._irc_server_connection.whois([nickname])
            
    def _get_user_hostmask(self, nickname, callback, *args):
        if not nickname in self._whoisuser_queue:
            self._whoisuser_queue[nickname] = []
        self._whoisuser_queue[nickname].append((callback, args))
        self._irc_server_connection.whois([nickname])
    
    def _handle_message(self, source, target, msg):
        logging.info("_handle_message:" + source + ":" + target + ":" + msg)
        
        self._identify_user(source, self._do_handle_message, source, target, msg)
    
    def _do_handle_message(self, from_username, source, target, msg):
        logging.info("_do_handle_message:" + from_username + ":" + source + ":" + target + ":" + msg)
        
        from_admin = self._is_admin(from_username)
        if from_admin:
            if self._try_admin_command(source, target, msg):
                return
        else:
            from_semi_admin = self._is_semi_admin(source)
            if from_semi_admin:
                if self._try_semi_admin_command(source, target, msg):
                    return
        
        for plugin in self._plugins.values():
            if (from_admin or not plugin.need_admin()) and plugin.check_permission(from_username):
                if target.startswith("#") and target in plugin.get_channels():
                    plugin.handle_highlight(from_username, source, target, msg)
                elif target == self._irc_server_connection.get_nickname():
                    plugin.handle_privmsg(from_username, source, target, msg)
    
    def _admin_quit(self, source, target):
        logging.info("_admin_quit")
        
        self._irc.disconnect_all()
        os.kill(os.getpid(), 9)
    
    def _admin_restart(self, source = None, target = None):
        logging.info("_admin_restart")
        
        self._irc.disconnect_all()
        os.execvp(sys.argv[0], tuple(sys.argv))
    
    def _admin_update(self, source, target):
        logging.info("_admin_update")
        
        for line in subprocess.check_output(["git", "--git-dir", os.path.join(os.path.split(os.path.realpath(sys.argv[0]))[0], ".git"), "pull"]).splitlines():
            self._irc_server_connection.privmsg(source.split("!")[0], line)
    
    def _admin_join_channel(self, source, target, channel):
        logging.info("_admin_join_channel:" + channel)
        
        channel = channel.rstrip().lstrip()
        self._irc_server_connection.join(channel)
        
    def _admin_leave_channel(self, source, target, channel = None):
        logging.info("_admin_leave_channel:" + str(channel))
        
        if channel == None and target.startswith("#"):
            channel = target
        channel = channel.rstrip().lstrip()
        self._irc_server_connection.part(channel)
    
    def _admin_save_channels(self, source, target):
        logging.info("_admin_save_channels")
        
        self._is_saving_channels = True
        self._irc_server_connection.whois([self._irc_server_connection.get_nickname()])
    
    def _admin_load_plugin(self, source, target, plugin_name):
        logging.info("_admin_load_plugin:" + source + ":" + target + ":" + plugin_name)
        
        self._load_plugin(plugin_name.rstrip().lstrip())

    def _admin_unload_plugin(self, source, target, plugin_name):
        logging.info("_admin_unload_plugin:" + source + ":" + target + ":" + plugin_name)
        
        plugin_name = plugin_name.rstrip().lstrip()
        if plugin_name in self._plugins:
            self._unload_plugin(plugin_name)
    
    def _admin_reload_config(self, source, target):
        logging.info("_admin_reload_config")
        
        self._load_config()
        self._load_plugins()
    
    def _try_admin_command(self, source, target, command):
        logging.info("_try_admin_command:" + source + ":" + target + ":" + command)
                
        for regexp in self._admin_commands:
            match_data = regexp.match(command)
            if match_data:
                self._admin_commands[regexp](*((source, target) + match_data.groups()))
                return True
        
        return False
    
    def _try_semi_admin_command(self, source, target, command):
        logging.info("_try_semi_admin_command:" + source + ":" + target + ":" + command)
                
        for regexp in self._semi_admin_commands:
            match_data = regexp.match(command)
            if match_data:
                self._semi_admin_commands[regexp](*((source, target) + match_data.groups()))
                return True
        
        return False
    
    def _on_irc_pubmsg(self, server_connection, event):
        logging.info("_on_irc_pubmsg:" + event.source + ":" + event.target + ":" + event.type + ":" + str(event.arguments))
        
        highlight_re = re.compile("^" + self._irc_server_connection.get_nickname() + "[:,\\ ](\\ *)(.*)$")
        highlight = highlight_re.match(event.arguments[0])
        if highlight:
            msg = highlight.group(2)
            self._handle_message(event.source, event.target, msg)
        
        self._identify_user(event.source, self._process_irc_pubmsg, event)
    
    def _process_irc_pubmsg(self, from_username, event):
        logging.info("_process_irc_pubmsg:" + from_username + ":" + event.source + ":" + event.target + ":" + event.type + ":" + str(event.arguments))
        
        from_admin = self._is_admin(from_username)
        for plugin in self._plugins.values():
            if event.target.startswith("#") and event.target in plugin.get_channels():
                if (from_admin or not plugin.need_admin()) and plugin.check_permission(from_username):
                    plugin.handle_channel_message(event.source, event.target, event.arguments[0])
    
    def _on_irc_action(self, server_connection, event):
        logging.info("_on_irc_action:" + event.source + ":" + event.target + ":" + event.type + ":" + str(event.arguments))
        
        self._identify_user(event.source, self._process_irc_action, event)
    
    def _process_irc_action(self, from_username, event):
        logging.info("_process_irc_action:" + from_username + ":" + event.source + ":" + event.target + ":" + event.type + ":" + str(event.arguments))
        
        from_admin = self._is_admin(from_username)
        for plugin in self._plugins.values():
            if event.target.startswith("#") and event.target in plugin.get_channels():
                if (from_admin or not plugin.need_admin()) and plugin.check_permission(from_username):
                    plugin.handle_channel_action(event.source, event.target, event.arguments[0])
    
    def _on_irc_pubnotice(self, server_connection, event):
        logging.info("_on_irc_pubnotice:" + event.source + ":" + event.target + ":" + event.type + ":" + str(event.arguments))
        
        self._identify_user(event.source, self._process_irc_pubnotice, event)
    
    def _process_irc_pubnotice(self, from_username, event):
        logging.info("_process_irc_pubnotice:" + from_username + ":" + event.source + ":" + event.target + ":" + event.type + ":" + str(event.arguments))
        
        from_admin = self._is_admin(from_username)
        for plugin in self._plugins.values():
            if event.target.startswith("#") and event.target in plugin.get_channels():
                if (from_admin or not plugin.need_admin()) and plugin.check_permission(from_username):
                    plugin.handle_channel_pubnotice(event.source, event.target, event.arguments[0])
    
    def _on_irc_privmsg(self, server_connection, event):
        logging.info("_on_irc_privmsg:" + event.source + ":" + event.target + ":" + event.type + ":" + str(event.arguments))
        
        self._handle_message(event.source, event.target, event.arguments[0])
    
    def _on_irc_whoischannels(self, server_connection, event):
        logging.info("_on_irc_whoischannels:" + event.source + ":" + event.target + ":" + event.type + ":" + str(event.arguments))
        
        if self._is_saving_channels and event.arguments[0] == self._irc_server_connection.get_nickname():
            self.config.set("General", "join_channels", ",".join([c.rstrip().lstrip() for c in event.arguments[1].split()]))
            self._save_config()
            self._is_saving_channels = False
    
    def _on_irc_user_login_info(self, server_connection, event):
        logging.info("_on_irc_user_login_info:" + event.source + ":" + event.target + ":" + event.type + ":" + str(event.arguments))
        
        self._nick_to_username_map[event.arguments[0]] = event.arguments[1]
    
    def _on_irc_whoisuser(self, server_connection, event):
        logging.info("_on_irc_whoisuser:" + event.source + ":" + event.target + ":" + event.type + ":" + str(event.arguments))
        
        nickname = event.arguments[0]
        ident = event.arguments[1]
        hostname = event.arguments[2]
                
        if nickname in self._whoisuser_queue:
            while len(self._whoisuser_queue[nickname]) > 0:
                callback, args = self._whoisuser_queue[nickname][0]
                del self._whoisuser_queue[nickname][0]
                callback("%s!%s@%s" % (nickname, ident, hostname), *args)
    
    def _on_irc_endofwhois(self, server_connection, event):
        logging.info("_on_irc_endofwhois:" + event.source + ":" + event.target + ":" + event.type + ":" + str(event.arguments))
        
        nickname = event.arguments[0]
        if not nickname in self._nick_to_username_map:
            self._nick_to_username_map[nickname] = ""
        
        if nickname in self._identify_user_queue:
            while len(self._identify_user_queue[nickname]) > 0:
                callback, args = self._identify_user_queue[nickname][0]
                del self._identify_user_queue[nickname][0]
                callback(self._nick_to_username_map[nickname], *args)
    
    def _on_irc_join(self, server_connection, event):
        logging.info("_on_irc_join:" + event.source + ":" + event.target + ":" + event.type + ":" + str(event.arguments))
        
        if event.source.split("!")[0] == self._irc_server_connection.get_nickname():
            return
        
        for plugin in self._plugins.values():
            if event.target.startswith("#") and event.target in plugin.get_channels():
                plugin.handle_channel_join(event.source, event.target)
    
    def _on_irc_part(self, server_connection, event):
        logging.info("_on_irc_part:" + event.source + ":" + event.target + ":" + event.type + ":" + str(event.arguments))
        
        if event.source.split("!")[0] == self._irc_server_connection.get_nickname():
            return
        
        for plugin in self._plugins.values():
            if event.target.startswith("#") and event.target in plugin.get_channels():
                plugin.handle_channel_part(event.source, event.target)
    
    def _on_irc_kick(self, server_connection, event):
        logging.info("_on_irc_kick:" + event.source + ":" + event.target + ":" + event.type + ":" + str(event.arguments))
        
        for plugin in self._plugins.values():
            if event.target.startswith("#") and event.target in plugin.get_channels() and event.type == "kick":
                plugin.handle_irc_kick(event.source, event.target, event.arguments[0], event.arguments[1])
        
    def _on_irc_mode(self, server_connection, event):
        logging.info("_on_irc_mode:" + event.source + ":" + event.target + ":" + event.type + ":" + str(event.arguments))
        
        for plugin in self._plugins.values():
            if event.target.startswith("#") and event.target in plugin.get_channels() and event.arguments[0] == "+b":
                plugin.handle_irc_ban(event.source, event.target, event.arguments[1])
            if event.target.startswith("#") and event.target in plugin.get_channels() and event.arguments[0] == "-b":
                plugin.handle_irc_unban(event.source, event.target, event.arguments[1])
        
        try:
            mode, mode_target = event.arguments
            if mode == u"-b":
                for plugin in self._plugins.values():
                    plugin.clear_mutes(event.target, mode_target)
        except:
            pass
        
    def _on_irc_whoreply(self, server_connection, event):
        logging.info("_on_irc_whoreply:" + event.source + ":" + event.target + ":" + event.type + ":" + str(event.arguments))
        
        channel, username, ident, server, nickname, flags, realname = event.arguments
        if flags in ["H@", "H~"] and nickname != "ChanServ":
            self._operators.setdefault(channel, []).append(nickname)
    
    def _connect(self):
        self._irc = irc.client.IRC()
        self._irc.add_global_handler("pubmsg", self._on_irc_pubmsg)
        self._irc.add_global_handler("privmsg", self._on_irc_privmsg)
        self._irc.add_global_handler("action", self._on_irc_action)
        self._irc.add_global_handler("pubnotice", self._on_irc_pubnotice)
        self._irc.add_global_handler("welcome", self._on_irc_welcome)
        self._irc.add_global_handler("900", self._on_irc_login)
        self._irc.add_global_handler("330", self._on_irc_user_login_info)
        self._irc.add_global_handler("whoisuser", self._on_irc_whoisuser)
        self._irc.add_global_handler("endofwhois", self._on_irc_endofwhois)
        self._irc.add_global_handler("whoischannels", self._on_irc_whoischannels)
        self._irc.add_global_handler("whoreply", self._on_irc_whoreply)
        self._irc.add_global_handler("join", self._on_irc_join)
        self._irc.add_global_handler("part", self._on_irc_part)
        self._irc.add_global_handler("mode", self._on_irc_mode)
        self._irc.add_global_handler("kick", self._on_irc_kick)
        self._irc_server_connection = self._irc.server()
        self._irc_server_connection.buffer_class.errors = 'replace'
        self._irc_server_connection.connect(
            server = self.config.get("General", "server"),
            nickname = self.config.get("General", "nickname"),
            username = self.config.get("General", "username"),
            port = self.config.getint("General", "port"),
            password = self.config.get("General", "password")
        )
        self._irc.execute_every(0.1, self._check_plugin_tasks)
        self._irc.execute_every(60, self._check_connection)
        self._irc.execute_every(60, self._check_nickname)
        self._irc.execute_every(60, self._check_operators)
    
    def _check_operators(self):
        logging.info("_check_operators")
        
        for channel in self.config.get("General", "join_channels").split(","):
            self._operators[channel] = []
            self._irc_server_connection.who(channel)
    
    def _check_nickname(self):
        logging.info("_check_nickname")
        
        if self._irc_server_connection.get_nickname() != self.config.get("General", "nickname"):
            self._on_irc_welcome(None, None)
            self._irc_server_connection.nick(self.config.get("General", "nickname"))
    
    def _check_connection(self):
        logging.info("_check_connection")

        if not self._irc_server_connection.is_connected():
            self._admin_restart()
    
    def _check_plugin_tasks(self):
        for plugin in self._plugins.values():
            plugin.process_tasks()
    
    def process_plugin_response(self, response):
        response.process(self._irc, self._irc_server_connection)
    
    def run(self):
        self._connect()
        self._irc.process_forever()
