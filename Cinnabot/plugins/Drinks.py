#! /usr/bin/python
# -*- coding=utf-8 -*-

from Cinnabot.BasePlugin import BasePlugin

DRINKS = [
    ("coffee", "cup", "pours"),
    ("tea", "cup", "pours"),
    ("beer", "pint", "serves"),
    ("martini", "glass", "serves"),
    ("whisky", "glass", "serves"),
    ("wine", "glass", "serves")
]

class DrinksPlugin(BasePlugin):
    def process_highlight(self, from_username, source, target, msg):
        words = [word.rstrip().lstrip() for word in msg.split(" ") if word.rstrip().lstrip() != ""]
        for drink, glass_type, verb in DRINKS:
            if " ".join([word.lower() for word in words]) in [drink, "make " + drink, "serve me " + drink, "serve me a " + drink, "serve " + drink, "make me " + drink, "make me a " + drink]:
                if target.startswith("#"):
                    resp_target = target
                else:
                    resp_target = source.split("!")[0]
                return self.action_response(resp_target, "%s %s a %s of %s" % (verb, source.split("!")[0], glass_type, drink))
    
    def process_privmsg(self, from_username, source, target, msg):
        return self.process_highlight(from_username, source, target, msg)
