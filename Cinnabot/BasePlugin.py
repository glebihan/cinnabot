#! /usr/bin/python
# -*- coding=utf-8 -*-

import logging
import threading
import sys
import re
import os
import time
import sqlite3

class PluginResponse(object):
    pass

class PluginPrivmsgResponse(PluginResponse):
    def __init__(self, target, msg):
        self._target = target
        self._msg = msg.replace("\n", " ").replace("\r", " ")
    
    def process(self, irc, irc_server_connection):
        if len(self._msg) <= 300:
            irc_server_connection.privmsg(self._target, self._msg)

class PluginActionResponse(PluginResponse):
    def __init__(self, target, msg):
        self._target = target
        self._msg = msg.replace("\n", " ").replace("\r", " ")
    
    def process(self, irc, irc_server_connection):
        irc_server_connection.action(self._target, self._msg)

class PluginNoticeResponse(PluginResponse):
    def __init__(self, target, msg):
        self._target = target
        self._msg = msg.replace("\n", " ").replace("\r", " ")
    
    def process(self, irc, irc_server_connection):
        irc_server_connection.notice(self._target, self._msg)

class PluginSajoinResponse(PluginResponse):
    def __init__(self, target, channel):
        self._target = target
        self._channel = channel
    
    def process(self, irc, irc_server_connection):
        irc_server_connection.send_raw("sajoin %s %s" % (self._target, self._channel))

class PluginKickResponse(PluginResponse):
    def __init__(self, target, channel, comment):
        self._target = target
        self._channel = channel
        self._comment = comment
    
    def process(self, irc, irc_server_connection):
        irc_server_connection.kick(self._channel, self._target, self._comment)

class PluginBanResponse(PluginResponse):
    def __init__(self, target, channel):
        self._target = target
        self._channel = channel
    
    def process(self, irc, irc_server_connection):
        irc_server_connection.mode(self._channel, "+b %s" % self._target)

class PluginUnbanResponse(PluginResponse):
    def __init__(self, target, channel):
        self._target = target
        self._channel = channel
    
    def process(self, irc, irc_server_connection):
        irc_server_connection.mode(self._channel, "-b %s" % self._target)

class TimedQuietResponse(PluginResponse):
    def __init__(self, plugin, channel, user, quiet_time, debug_mode):
        self._plugin = plugin
        self._channel = channel
        self._user = user
        self._quiet_time = quiet_time
        self._debug_mode = debug_mode
    
    def process(self, irc, irc_server_connection):
        mute_host = self._user.split("@")[1]
        mute_mask = "*!*@%s" % mute_host
        if not mute_host in self._plugin.muted_hosts.setdefault(self._channel, []):
            self._plugin.muted_hosts.setdefault(self._channel, []).append(mute_host)
            if not self._debug_mode:
                irc_server_connection.mode(self._channel, "+b m:%s" % mute_mask)
            irc.execute_delayed(self._quiet_time, self._unprocess, (irc, irc_server_connection, mute_host, mute_mask))
    
    def _unprocess(self, irc, irc_server_connection, mute_host, mute_mask):
        while mute_host in self._plugin.muted_hosts.setdefault(self._channel, []):
            del self._plugin.muted_hosts[self._channel][self._plugin.muted_hosts[self._channel].index(mute_host)]
        if not self._debug_mode:
            irc_server_connection.mode(self._channel, "-b m:%s" % mute_mask)

class PluginTask(object):
    def __init__(self, task_id, callback, method, *args):
        self._task_id = task_id
        self._callback = callback
        self._method = method
        self._args = args
        self._result = None
        self._lock = threading.Lock()
    
    def run(self):
        self._thread = threading.Thread(None, self._do_run, None, (self._method, self._args))
        self._thread.start()
    
    def _get_result(self):
        self._lock.acquire()
        res = self._result
        self._lock.release()
        return res
    def _set_result(self, value):
        self._lock.acquire()
        self._result = value
        self._lock.release()
    result = property(_get_result, _set_result)
    
    def _do_run(self, method, args):
        try:
            self.result = method(*args)
        except:
            self.result = sys.exc_info()
    
    def is_alive(self):
        return self._thread.is_alive()

class BasePlugin(object):
    def __init__(self, bot, plugin_name):
        self._bot = bot
        self._plugin_name = plugin_name
        self._task_id = 0
        self._tasks = {}
        self.muted_hosts = {}
        self._db_lock = threading.Lock()
    
    def get_help(self):
        return {}
    
    def unload(self):
        pass
    
    def _get_config(self, key):
        return self._bot.config.get("Plugin/" + self._plugin_name, key)
    
    def _set_config(self, key, value):
        self._bot.config.set("Plugin/" + self._plugin_name, key, value)
        self._bot._save_config()
    
    def _get_config_options(self):
        return self._bot.config.options("Plugin/" + self._plugin_name)
    
    def _get_boolean_config(self, key):
        return self._bot.config.getboolean("Plugin/" + self._plugin_name, key)
    
    def _has_config(self, key):
        return self._bot.config.has_option("Plugin/" + self._plugin_name, key)
    
    def _remove_config(self, key):
        return self._bot.config.remove_option("Plugin/" + self._plugin_name, key)
    
    def need_admin(self):
        return self._has_config("need_admin") and self._get_boolean_config("need_admin")
    
    def get_channels(self):
        if self._has_config("channels"):
            return self._get_config("channels").split(",")
        else:
            return []
    
    def check_permission(self, username):
        allowed_usernames = []
        for key in self._get_config_options():
            if key.startswith("allowed_username"):
                allowed_usernames.append(self._get_config(key))
        if len(allowed_usernames) == 0:
            return True
        return username != "" and username in allowed_usernames
    
    def _start_task(self, method, *args):
        self._task_id += 1
        task = PluginTask(self._task_id, None, method, *args)
        self._tasks[self._task_id] = task
        task.run()
    
    def _prevent_handle(self, handle_type, msg):
        i = 1
        while self._has_config("prevent_%s_mask%d" % (handle_type, i)):
            if re.compile(self._get_config("prevent_%s_mask%d" % (handle_type, i))).search(msg):
                return True
            i += 1
        return False
    
    def handle_highlight(self, from_username, source, target, msg):
        logging.info("plugin_handle_highlight:" + self._plugin_name + ":" + from_username + ":" + source + ":" + target + ":" + msg)
        
        if hasattr(self, "process_highlight"):
            self._start_task(self.process_highlight, from_username, source, target, msg)
        
    def handle_privmsg(self, from_username, source, target, msg):
        logging.info("plugin_handle_privmsg:" + self._plugin_name + ":" + from_username + ":" + source + ":" + target + ":" + msg)
        
        if hasattr(self, "process_privmsg"):
            self._start_task(self.process_privmsg, from_username, source, target, msg)
    
    def handle_channel_message(self, source, target, msg):
        logging.info("plugin_handle_channel_message:" + self._plugin_name + ":" + source + ":" + target + ":" + msg)
        
        if hasattr(self, "process_channel_message") and not self._prevent_handle("handle_channel_message", msg):
            self._start_task(self.process_channel_message, source, target, msg)
            
    def handle_channel_action(self, source, target, msg):
        logging.info("plugin_handle_channel_action:" + self._plugin_name + ":" + source + ":" + target + ":" + msg)
        
        if hasattr(self, "process_channel_action"):
            self._start_task(self.process_channel_action, source, target, msg)
    
    def handle_channel_pubnotice(self, source, target, msg):
        logging.info("plugin_handle_channel_pubnotice:" + self._plugin_name + ":" + source + ":" + target + ":" + msg)
        
        if hasattr(self, "process_channel_pubnotice"):
            self._start_task(self.process_channel_pubnotice, source, target, msg)
    
    def handle_channel_join(self, source, target):
        logging.info("plugin_handle_channel_join:" + self._plugin_name + ":" + source + ":" + target)
        
        if hasattr(self, "process_channel_join"):
            self._start_task(self.process_channel_join, source, target)
    
    def handle_channel_part(self, source, target):
        logging.info("plugin_handle_channel_part:" + self._plugin_name + ":" + source + ":" + target)
        
        if hasattr(self, "process_channel_part"):
            self._start_task(self.process_channel_part, source, target)
        
    def handle_irc_kick(self, source, target, nickname, comment):
        logging.info("plugin_handle_irc_kick:" + self._plugin_name + ":" + source + ":" + target + ":" + nickname + ":" + comment)
        
        if hasattr(self, "process_irc_kick"):
            self._start_task(self.process_irc_kick, source, target, nickname, comment)
            
    def handle_irc_ban(self, source, target, mask):
        logging.info("plugin_handle_irc_ban:" + self._plugin_name + ":" + source + ":" + target + ":" + mask)
        
        if hasattr(self, "process_irc_ban"):
            self._start_task(self.process_irc_ban, source, target, mask)
    
    def handle_irc_unban(self, source, target, mask):
        logging.info("plugin_handle_irc_unban:" + self._plugin_name + ":" + source + ":" + target + ":" + mask)
        
        if hasattr(self, "process_irc_unban"):
            self._start_task(self.process_irc_unban, source, target, mask)
    
    def privmsg_response(self, target, msg):
        return PluginPrivmsgResponse(target, msg)
    
    def action_response(self, target, msg):
        return PluginActionResponse(target, msg)
        
    def notice_response(self, target, msg):
        return PluginNoticeResponse(target, msg)
        
    def sajoin_response(self, target, channel):
        return PluginSajoinResponse(target, channel)
        
    def wallchop_response(self, target, msg):
        if self._has_config("always_wallchop_users"):
            dests = self._get_config("always_wallchop_users").split(",") + self._bot._operators.setdefault(target, [])
        else:
            dests = self._bot._operators.setdefault(target, [])
        if len(dests) > 0:
            return PluginNoticeResponse(",".join(dests), msg)
    
    def timed_quiet_response(self, channel, user, quiet_time, debug_mode):
        return TimedQuietResponse(self, channel, user, quiet_time, debug_mode)
    
    def kick_response(self, nickname, channel, comment = ""):
        return PluginKickResponse(nickname, channel, comment)
    
    def ban_response(self, mask, channel):
        return PluginBanResponse(mask, channel)

    def unban_response(self, mask, channel):
        return PluginUnbanResponse(mask, channel)
    
    def process_tasks(self):
        for task_id in self._tasks.keys():
            task = self._tasks[task_id]
            if not task.is_alive():
                if isinstance(task.result, PluginResponse):
                    self._bot.process_plugin_response(task.result)
                elif type(task.result) == list:
                    if len([i for i in task.result if not isinstance(i, PluginResponse)]) > 0:
                        logging.warn("Incorrect plugin response : " + str(task.result))
                    else:
                        for i in task.result:
                            self._bot.process_plugin_response(i)
                elif task.result != None:
                    logging.warn("Incorrect plugin response : " + str(task.result))
                del self._tasks[task_id]
    
    def clear_mutes(self, channel, mute_mask):
        logging.info("plugin_clear_mutes:" + self._plugin_name + ":" + channel + ":" + mute_mask)
        
        mute_host = mute_mask.split("@")[1]
        while mute_host in self.muted_hosts.setdefault(channel, []):
            del self.muted_hosts[channel][self.muted_hosts[channel].index(mute_host)]
    
    def _log(self, msg):
        filename = os.path.join(os.getenv('HOME'), '.config', 'cinnabot', self._plugin_name + '.log')
        if os.path.exists(filename):
            f = open(filename, 'a')
        else:
            f = open(filename, 'w')
        f.write(time.strftime('%Y-%m-%d %H:%M:%S') + ' ' + msg + '\n')
        f.close()
    
    def _get_db_connection(self):
        filename = os.path.join(os.getenv('HOME'), '.config', 'cinnabot', self._plugin_name + '.sqlite')
        return sqlite3.connect(filename)
    
    def _get_db_version(self):
        self._db_query("CREATE TABLE IF NOT EXISTS `global_data` (`key` TEXT PRIMARY KEY, `value` TEXT)")
        res = self._db_query("SELECT `value` FROM `global_data` WHERE `key` = 'version'")
        if res:
            return int(res[0][0])
        else:
            return 0
    
    def _set_db_version(self, version):
        self._db_query("REPLACE INTO `global_data` (`key`, `value`) VALUES ('version', ?)", (version,))
    
    def init_db(self, db_upgrades):
        version = self._get_db_version()
        upgrades = [i for i in db_upgrades if i > version]
        if upgrades:
            upgrades.sort()
            for i in upgrades:
                for sql in db_upgrades[i]:
                    self._db_query(sql)
            self._set_db_version(upgrades[-1])
    
    def _db_query(self, *args):
        self._db_lock.acquire()
        conn = self._get_db_connection()
        cur = conn.cursor()
        cur.execute(*args)
        res = cur.fetchall()
        cur.close()
        conn.commit()
        self._db_lock.release()
        return res
