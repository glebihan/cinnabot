#! /usr/bin/python
# -*- coding=utf-8 -*-

from Cinnabot.BasePlugin import BasePlugin
import time

class FloodDetectionPlugin(BasePlugin):
    def __init__(self, bot, plugin_name):
        BasePlugin.__init__(self, bot, plugin_name)
        self._messages_by_source = {}
        self._messages_by_source2 = {}
        self._last_sent_warning = {}
        self._quiet_times = {}
        
    def process_channel_pubnotice(self, source, target, msg):
        return self.process_channel_message(source, target, msg)
        
    def process_channel_action(self, source, target, msg):
        return self.process_channel_message(source, target, msg)
        
    def process_channel_message(self, source, target, msg):
        if source.split("@")[1] in self.muted_hosts:
            return
                    
        resp = []
        self._messages_by_source.setdefault(source, []).append(time.time())
        self._messages_by_source2.setdefault(source, []).append(time.time())
        self._messages_by_source[source] = self._messages_by_source[source][-int(self._get_config("nb_messages")):]
        self._messages_by_source2[source] = self._messages_by_source2[source][-int(self._get_config("nb_messages2")):]
        
        if (len(self._messages_by_source[source]) == int(self._get_config("nb_messages")) and time.time() - min(self._messages_by_source[source]) < int(self._get_config("interval"))) or (len(self._messages_by_source2[source]) == int(self._get_config("nb_messages2")) and time.time() - min(self._messages_by_source2[source]) < int(self._get_config("interval2"))):
            if time.time() - self._last_sent_warning.setdefault(source, 0) > 600:
                if self._get_config("debug_mode") != "true":
                    resp.append(self.privmsg_response(target, "%s, Please don't paste in here when there's more than 3 lines. Use http://dpaste.com/ instead. Thank you !" % source.split("!")[0]))
                self._last_sent_warning[source] = time.time()
            if not source in self._quiet_times:
                self._quiet_times[source] = int(self._get_config("quiet_time"))
                if self._get_config("debug_mode") == "true":
                    resp.append(self.wallchop_response(target, "[@%s] Flood from user %s in %s" % (target, source.split("!")[0], target)))
            else:
                self._quiet_times[source] = 2 * self._quiet_times[source]
                resp.append(self.wallchop_response(target, "[@%s] Flood from user %s in %s" % (target, source.split("!")[0], target)))
            resp.append(self.timed_quiet_response(target, source, self._quiet_times[source], self._get_config("debug_mode") == "true"))
        
        return resp
