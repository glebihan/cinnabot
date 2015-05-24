#! /usr/bin/python
# -*- coding=utf-8 -*-

from Cinnabot.BasePlugin import BasePlugin
import subprocess

class ExternalScriptsPlugin(BasePlugin):
    def __init__(self, bot, plugin_name):
        BasePlugin.__init__(self, bot, plugin_name)
    
    def _run_command(self, from_username, resp_target, command_name, exec_command, exec_params):
        status = subprocess.call([exec_command] + exec_params)
        if status != 0:
            resp_msg = "\x0305\x02%s failed\x0f" % command_name
            if resp_target.startswith("#"):
                resp_msg = from_username + ", " + resp_msg
            return self.privmsg_response(resp_target, resp_msg)
    
    def process_highlight(self, from_username, source, target, msg):
        res = []
        config_options = self._get_config_options()
        i = 1
        while "command%d" % i in config_options:
            command = self._get_config("command%d" % i)
            command_name, start_feedback, exec_command = command.split(":", 3)
            if msg.split(" ")[0] == command_name:
                if target.startswith("#"):
                    resp_target = target
                else:
                    resp_target = source.split("!")[0]
                self._start_task(self._run_command, from_username, resp_target, command_name, exec_command, msg.split(" ")[1:])
                res.append(self.privmsg_response(resp_target, start_feedback))
            i += 1
        return res
    
    def process_privmsg(self, from_username, source, target, msg):
        return self.process_highlight(from_username, source, target, msg)
