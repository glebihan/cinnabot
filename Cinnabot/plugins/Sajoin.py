#! /usr/bin/python
# -*- coding=utf-8 -*-

from Cinnabot.BasePlugin import BasePlugin

class SajoinPlugin(BasePlugin):
    def __init__(self, bot, plugin_name):
        BasePlugin.__init__(self, bot, plugin_name)
        self._sajoin_list = {}
        
    def process_privmsg(self, from_username, source, target, msg):
        words = msg.split()
        if len(words) == 3 and words[0].lower() == "sajoin" and words[2][0] == "#" and not words[1] in self._sajoin_list.setdefault(words[2], []):
            self._sajoin_list.setdefault(words[2], []).append(words[1])
            return self.sajoin_response(words[1], words[2])
        
        if len(words) == 3 and words[0].lower() == "unsajoin" and words[2][0] == "#" and words[1] in self._sajoin_list.setdefault(words[2], []):
            while words[1] in self._sajoin_list[words[2]]:
                i = self._sajoin_list[words[2]].index(words[1])
                del self._sajoin_list[words[2]][i]
    
    def process_channel_part(self, source, target):
        if source.split("!")[0] in self._sajoin_list.setdefault(target, []):
            return self.sajoin_response(source.split("!")[0], target)
