#! /usr/bin/python
# -*- coding=utf-8 -*-

from Cinnabot.BasePlugin import BasePlugin
import os

class ExternalScriptsPlugin(BasePlugin):
    def __init__(self, bot, plugin_name):
        BasePlugin.__init__(self, bot, plugin_name)
    
    def process_highlight(self, from_username, source, target, msg):
        res = []
        config_options = self._get_config_options()
        i = 1
        while "command%d" % i in config_options:
            command = self._get_config("command%d" % i)
            command_name, start_feedback, exec_command = command.split(":", 3)
            if msg.split(" ")[0] == command_name:
                if os.fork() == 0:
                    os.execvp(exec_command, (exec_command,) + tuple(msg.split(" ")[1:]))
                else:
                    if target.startswith("#"):
                        resp_target = target
                    else:
                        resp_target = source.split("!")[0]
                    res.append(self.privmsg_response(resp_target, start_feedback))
            i += 1
        return res
    
    def process_privmsg(self, from_username, source, target, msg):
        return self.process_highlight(from_username, source, target, msg)
