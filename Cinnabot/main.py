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
    "^\\ *reload\ config\\ *$": "reload_config",
    "^\\ *join\\ channel(\\ +#+[a-zA-Z0-9\\-\\_]+)\\ *$": "join_channel",
    "^\\ *join(\\ +#+[a-zA-Z0-9\\-\\_]+)\\ *$": "join_channel",
    "^\\ *leave\\ channel(\\ +#+[a-zA-Z0-9\\-\\_]+)?\\ *$": "leave_channel",
    "^\\ *leave(\\ +#+[a-zA-Z0-9\\-\\_]+)?\\ *$": "leave_channel",
    "^\\ *save channels\\ *$": "save_channels",
    "^\\ *load plugin(\\ +[a-zA-Z]+)\\ *$": "load_plugin",
    "^\\ *unload plugin(\\ +[a-zA-Z]+)\\ *$": "unload_plugin"
}

class Cinnabot(object):
    def __init__(self):
        self._parse_cli_options()
        self._load_config()
        
        self._admin_commands = {}
        for regexp in ADMIN_COMMANDS_RE:
            self._admin_commands[re.compile(regexp)] = getattr(self, "_admin_" + ADMIN_COMMANDS_RE[regexp])
        
        self._is_saving_channels = False
        
        self._plugins = {}
    
    def _parse_cli_options(self):
        optparser = optparse.OptionParser()
        optparser.add_option('-c', '--config-file', dest = "config_file", default = os.path.join(os.getenv("HOME"), ".config", "cinnabot", "cinnabot.conf"))
        optparser.add_option("-d", "--debug-level", dest = "debug_level", type = "int", default = 2)
        self.cli_options = optparser.parse_args()[0]
        
        self.cli_options.config_file = os.path.realpath(self.cli_options.config_file)
        logging.getLogger().setLevel(DEBUG_LEVELS[self.cli_options.debug_level])
    
    def _load_config(self):
        self.config = ConfigParser.RawConfigParser()
        self.config.read(self.cli_options.config_file)
        
        self._admin_masks = []
        for key in self.config.options("Admin"):
            if key.startswith("admin_mask"):
                self._admin_masks.append(re.compile(self.config.get("Admin", key)))
    
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
    
    def _is_admin(self, mask):
        for admin_mask in self._admin_masks:
            if admin_mask.match(mask):
                return True
        return False
    
    def _handle_message(self, source, target, msg):
        logging.info("_handle_message:" + source + ":" + target + ":" + msg)
        
        from_admin = self._is_admin(source)
        
        if from_admin:
            if self._try_admin_command(source, target, msg):
                return
        
        for plugin in self._plugins.values():
            if (from_admin or not plugin.need_admin()) and plugin.check_permission(source):
                if target.startswith("#") and target in plugin.get_channels():
                    plugin.handle_highlight(source, target, msg)
                elif target == self._irc_server_connection.get_nickname():
                    plugin.handle_privmsg(source, target, msg)
    
    def _admin_quit(self, source, target):
        logging.info("_admin_quit")
        
        self._irc.disconnect_all()
        os.kill(os.getpid(), 9)
    
    def _admin_restart(self, source, target):
        logging.info("_admin_restart")
        
        self._irc.disconnect_all()
        os.execvp(sys.argv[0], tuple(sys.argv))
    
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
    
    def _on_irc_pubmsg(self, server_connection, event):
        logging.info("_on_irc_pubmsg:" + event.source + ":" + event.target + ":" + event.type + ":" + str(event.arguments))
        
        highlight_re = re.compile("^" + self._irc_server_connection.get_nickname() + "[:,\\ ](\\ *)(.*)$")
        highlight = highlight_re.match(event.arguments[0])
        if highlight:
            msg = highlight.group(2)
            self._handle_message(event.source, event.target, msg)
        else:
            from_admin = self._is_admin(event.source)
            for plugin in self._plugins.values():
                if (from_admin or not plugin.need_admin()) and plugin.check_permission(event.source):
                    if event.target.startswith("#") and event.target in plugin.get_channels():
                        plugin.handle_channel_message(event.source, event.target, event.arguments[0])
    
    def _on_irc_privmsg(self, server_connection, event):
        logging.info("_on_irc_privmsg:" + event.source + ":" + event.target + ":" + event.type + ":" + str(event.arguments))
        
        self._handle_message(event.source, event.target, event.arguments[0])
    
    def _on_irc_whoischannels(self, server_connection, event):
        logging.info("_on_irc_whoischannels:" + event.source + ":" + event.target + ":" + event.type + ":" + str(event.arguments))
        
        if self._is_saving_channels and event.arguments[0] == self._irc_server_connection.get_nickname():
            self.config.set("General", "join_channels", ",".join([c.rstrip().lstrip() for c in event.arguments[1].split()]))
            self._save_config()
            self._is_saving_channels = False
    
    def _connect(self):
        self._irc = irc.client.IRC()
        self._irc.add_global_handler("pubmsg", self._on_irc_pubmsg)
        self._irc.add_global_handler("privmsg", self._on_irc_privmsg)
        self._irc.add_global_handler("welcome", self._on_irc_welcome)
        self._irc.add_global_handler("900", self._on_irc_login)
        self._irc.add_global_handler("whoischannels", self._on_irc_whoischannels)
        self._irc_server_connection = self._irc.server()
        self._irc_server_connection.connect(
            server = self.config.get("General", "server"),
            nickname = self.config.get("General", "nickname"),
            username = self.config.get("General", "username"),
            port = self.config.getint("General", "port"),
            password = self.config.get("General", "password")
        )
        self._irc.execute_every(0.1, self._check_plugin_tasks)
    
    def _check_plugin_tasks(self):
        for plugin in self._plugins.values():
            plugin.process_tasks()
    
    def process_plugin_response(self, response):
        response.process(self._irc, self._irc_server_connection)
    
    def run(self):
        self._connect()
        self._irc.process_forever()
