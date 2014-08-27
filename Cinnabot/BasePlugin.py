#! /usr/bin/python
# -*- coding=utf-8 -*-

import logging
import threading
import sys
import re

MUTED_MASKS = []

class PluginResponse(object):
    pass

class PluginPrivmsgResponse(PluginResponse):
    def __init__(self, target, msg):
        self._target = target
        self._msg = msg
    
    def process(self, irc, irc_server_connection):
        if len(self._msg) <= 300:
            irc_server_connection.privmsg(self._target, self._msg)

class PluginActionResponse(PluginResponse):
    def __init__(self, target, msg):
        self._target = target
        self._msg = msg
    
    def process(self, irc, irc_server_connection):
        irc_server_connection.action(self._target, self._msg)

class PluginNoticeResponse(PluginResponse):
    def __init__(self, target, msg):
        self._target = target
        self._msg = msg
    
    def process(self, irc, irc_server_connection):
        irc_server_connection.notice(self._target, self._msg)

class TimedQuietResponse(PluginResponse):
    def __init__(self, channel, user, quiet_time):
        self._channel = channel
        self._user = user
        self._quiet_time = quiet_time
    
    def process(self, irc, irc_server_connection):
        mute_mask = "*!*@%s" % self._user.split("@")[1]
        if not mute_mask in MUTED_MASKS:
            MUTED_MASKS.append(mute_mask)
            irc_server_connection.mode(self._channel, "+b m:%s" % mute_mask)
            irc.execute_delayed(self._quiet_time, self._unprocess, (irc, irc_server_connection, mute_mask))
    
    def _unprocess(self, irc, irc_server_connection, mute_mask):
        while mute_mask in MUTED_MASKS:
            del MUTED_MASKS[MUTED_MASKS.index(mute_mask)]
        irc_server_connection.mode(self._channel, "-b m:%s" % mute_mask)
        irc_server_connection.privmsg("ChanServ", "unquiet %s %s" % (self._channel, mute_mask))

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
    
    def unload(self):
        pass
    
    def _get_config(self, key):
        return self._bot.config.get("Plugin/" + self._plugin_name, key)
    
    def _get_config_options(self):
        return self._bot.config.options("Plugin/" + self._plugin_name)
    
    def _get_boolean_config(self, key):
        return self._bot.config.getboolean("Plugin/" + self._plugin_name, key)
    
    def _has_config(self, key):
        return self._bot.config.has_option("Plugin/" + self._plugin_name, key)
    
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
        
        if hasattr(self, "process_channel_message"):
            self._start_task(self.process_channel_message, source, target, msg)
    
    def handle_channel_join(self, source, target):
        logging.info("plugin_handle_channel_join:" + self._plugin_name + ":" + source + ":" + target)
        
        if hasattr(self, "process_channel_join"):
            self._start_task(self.process_channel_join, source, target)
    
    def privmsg_response(self, target, msg):
        return PluginPrivmsgResponse(target, msg)
    
    def action_response(self, target, msg):
        return PluginActionResponse(target, msg)
        
    def notice_response(self, target, msg):
        return PluginNoticeResponse(target, msg)
    
    def timed_quiet_response(self, channel, user, quiet_time):
        return TimedQuietResponse(channel, user, quiet_time)
    
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
