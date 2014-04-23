#! /usr/bin/python
# -*- coding=utf-8 -*-

import feedparser
import logging
from Cinnabot.BasePlugin import BasePlugin

class SegfaultPlugin(BasePlugin):
    def __init__(self, bot, plugin_name):
        BasePlugin.__init__(self, bot, plugin_name)
        
        bot._irc.execute_every(300, self._check_new_posts)
        self._check_new_posts()
        
        self._known_posts = []
        self._has_run = False
    
    def unload(self):
        self._unloaded = True
    
    def _check_new_posts(self):
        if hasattr(self, "_unloaded") and self._unloaded:
            return
        
        self._start_task(self._do_check_new_posts)
    
    def _do_check_new_posts(self):
        logging.info("SegfaultPlugin:_do_check_new_posts")
        
        feed = feedparser.parse("http://segfault.linuxmint.com/feed/")
        for item in feed["items"]:
            if not self._has_run:
                self._known_posts.append(item["id"])
            elif item["id"] not in self._known_posts:
                self._known_posts.append(item["id"])
                return self.privmsg_response(self._get_config("output_channel"), u"[\x0313Segfault\x0f] \x0314New post\x0f \x0315%s\x0f: %s \x0302\x1f%s\x0f" % (item["author"], item["title"], item["link"]))
        
        self._has_run = True
