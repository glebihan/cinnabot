#! /usr/bin/python
# -*- coding=utf-8 -*-

from Cinnabot.BasePlugin import BasePlugin
import logging
import json
import httplib2
import os
from launchpadlib.launchpad import Launchpad

class LaunchpadBuildsPlugin(BasePlugin):
    def __init__(self, bot, plugin_name):
        BasePlugin.__init__(self, bot, plugin_name)
        
        bot._irc.execute_every(900, self._check_failed_builds)
        self._check_failed_builds()
        
        self._known_builds = {}
        self._has_run = False
        self._last_date = None
    
    def unload(self):
        self._unloaded = True
    
    def _check_failed_builds(self):
        if hasattr(self, "_unloaded") and self._unloaded:
            return
        
        self._start_task(self._do_check_failed_builds)
    
    def _shorten_url(self, url):
        try:
            c = httplib2.Http()
            resp, content = c.request("https://www.googleapis.com/urlshortener/v1/url?key=" + self._get_config("google_url_shortener_api_key"), "POST", headers = {"Content-Type": "application/json"}, body = json.dumps({"longUrl": url}))
            res = json.loads(content)["id"]
        except:
            res = url
        return res
    
    def _do_check_failed_builds(self):
        logging.info("LaunchpadBuildsPlugin:_do_check_failed_builds")
        
        launchpad = Launchpad.login_anonymously('cinnabot', 'production', os.path.join(os.getenv("HOME"), ".launchpadlib", "cache"))
        ppa = launchpad.load("https://api.launchpad.net/1.0/~gwendal-lebihan-dev/+archive/cinnamon-nightly")
        ppa_sources = ppa.getPublishedSources(status = "Published")
        
        for source in ppa_sources:
            builds = source.getBuilds()
            for build in builds:
                if not self._has_run:
                    self._known_builds[build.self_link] = build.datebuilt
                else:
                    if not build.self_link in self._known_builds or self._known_builds[build.self_link] != build.datebuilt:
                        self._known_builds[build.self_link] = build.datebuilt
                        if build.buildstate == "Failed to build":
                            return self.privmsg_response(self._get_config("output_channel"), u"[\x0313%s\x0f] \x0305\x02Failed build: \x0f%s \x0302\x1f%s\x0f, build log : \x0302\x1f%s\x0f" % (source.source_package_name, build.title, self._shorten_url(build.web_link), self._shorten_url(build.build_log_url)))
        self._has_run = True
