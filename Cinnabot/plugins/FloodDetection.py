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
        
    def process_channel_message(self, source, target, msg):
        resp = []
        self._messages_by_source.setdefault(source, []).append(time.time())
        self._messages_by_source2.setdefault(source, []).append(time.time())
        self._messages_by_source[source] = self._messages_by_source[source][-int(self._get_config("nb_messages")):]
        self._messages_by_source2[source] = self._messages_by_source2[source][-int(self._get_config("nb_messages2")):]
        
        if (len(self._messages_by_source[source]) == int(self._get_config("nb_messages")) and time.time() - min(self._messages_by_source[source]) < int(self._get_config("interval"))) or (len(self._messages_by_source2[source]) == int(self._get_config("nb_messages2")) and time.time() - min(self._messages_by_source2[source]) < int(self._get_config("interval2"))):
            if time.time() - self._last_sent_warning.setdefault(source, 0) > 60:
                resp.append(self.privmsg_response(target, "%s, Please don't paste in here when there's more than 3 lines. Use http://dpaste.com/ instead. Thank you !" % source.split("!")[0]))
                self._last_sent_warning[source] = time.time()
            resp.append(self.timed_quiet_response(target, source, int(self._get_config("quiet_time"))))
        
        return resp
