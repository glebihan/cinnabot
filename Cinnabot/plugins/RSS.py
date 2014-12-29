#! /usr/bin/python
# -*- coding=utf-8 -*-

import feedparser
import logging
from Cinnabot.BasePlugin import BasePlugin

class RSSPlugin(BasePlugin):
    def __init__(self, bot, plugin_name):
        BasePlugin.__init__(self, bot, plugin_name)
        
        self._feed_urls = []
        for i in self._get_config_options():
            if i.startswith("feed_url"):
                self._feed_urls.append(self._get_config(i))
        
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
        logging.info("RSSPlugin:_do_check_new_posts")
        
        res = []
        for url in self._feed_urls:
            feed = feedparser.parse(url)
            for item in feed["items"]:
                if not self._has_run:
                    self._known_posts.append(item["id"])
                elif item["id"] not in self._known_posts:
                    self._known_posts.append(item["id"])
                    if "author" in item:
                        res.append(self.privmsg_response(self._get_config("output_channel"), u"[\x0313%s\x0f] \x0314New post\x0f \x0315%s\x0f: %s \x0302\x1f%s\x0f" % (feed["feed"]["title"], item["author"], item["title"], item["link"])))
                    else:
                        res.append(self.privmsg_response(self._get_config("output_channel"), u"[\x0313%s\x0f] \x0314New post\x0f %s \x0302\x1f%s\x0f" % (feed["feed"]["title"], item["title"], item["link"])))
                    return res
        
        self._has_run = True
        
        return res
