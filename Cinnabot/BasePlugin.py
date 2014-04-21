#! /usr/bin/python
# -*- coding=utf-8 -*-

import logging
import threading
import sys
import re

class PluginResponse(object):
    pass

class PluginPrivmsgResponse(PluginResponse):
    def __init__(self, target, msg):
        self._target = target
        self._msg = msg
    
    def process(self, irc, irc_server_connection):
        irc_server_connection.privmsg(self._target, self._msg)

class PluginActionResponse(PluginResponse):
    def __init__(self, target, msg):
        self._target = target
        self._msg = msg
    
    def process(self, irc, irc_server_connection):
        irc_server_connection.action(self._target, self._msg)

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
    
    def handle_highlight(self, source, target, msg):
        logging.info("plugin_handle_highlight:" + self._plugin_name + ":" + source + ":" + target + ":" + msg)
        
        if hasattr(self, "process_highlight"):
            self._start_task(self.process_highlight, source, target, msg)
        
    def handle_privmsg(self, source, target, msg):
        logging.info("plugin_handle_privmsg:" + self._plugin_name + ":" + source + ":" + target + ":" + msg)
        
        if hasattr(self, "process_privmsg"):
            self._start_task(self.process_privmsg, source, target, msg)
    
    def handle_channel_message(self, source, target, msg):
        logging.info("plugin_handle_channel_message:" + self._plugin_name + ":" + source + ":" + target + ":" + msg)
        
        if hasattr(self, "process_channel_message"):
            self._start_task(self.process_channel_message, source, target, msg)
    
    def privmsg_response(self, target, msg):
        return PluginPrivmsgResponse(target, msg)
    
    def action_response(self, target, msg):
        return PluginActionResponse(target, msg)
    
    def process_tasks(self):
        for task_id in self._tasks.keys():
            task = self._tasks[task_id]
            if not task.is_alive():
                if isinstance(task.result, PluginResponse):
                    self._bot.process_plugin_response(task.result)
                elif task.result != None:
                    logging.warn("Incorrect plugin response : " + str(task.result))
                del self._tasks[task_id]
