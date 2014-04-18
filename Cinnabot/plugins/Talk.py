#! /usr/bin/python
# -*- coding=utf-8 -*-

from Cinnabot.BasePlugin import BasePlugin
import re

REG_EXP = re.compile("^(#+[a-zA-Z0-9\\-\\_]+)\\ +(.*)$")

class TalkPlugin(BasePlugin):
    def process_privmsg(self, source, target, msg):
        match = REG_EXP.match(msg)
        if match:
            channel, resp = match.groups()
            return self.privmsg_response(channel, resp)
