#! /usr/bin/python
# -*- coding=utf-8 -*-

from Cinnabot.BasePlugin import BasePlugin
import logging
import httplib2
from distutils.version import LooseVersion

class UpstreamReleasesPlugin(BasePlugin):
    def __init__(self, bot, plugin_name):
        BasePlugin.__init__(self, bot, plugin_name)
        
        self._known_releases = {}
        
        bot._irc.execute_every(3600, self._check_releases)
        self._check_releases()
    
    def _check_releases(self):
        self._start_task(self._do_check_releases, "firefox")
        self._start_task(self._do_check_releases, "thunderbird")
        self._start_task(self._do_check_releases, "virtualbox")
    
    def _do_check_releases(self, package):
        try:
            version_list = []
            c = httplib2.Http()
            if package == "virtualbox":
                resp, content = c.request("http://download.virtualbox.org/virtualbox/")
                split_string = "<A"
                ignore_lines_start = 0
            elif package == "firefox":
                resp, content = c.request("https://download-installer.cdn.mozilla.net/pub/firefox/releases/")
                split_string = "<tr"
                ignore_lines_start = 4
            else:
                resp, content = c.request("https://download-installer.cdn.mozilla.net/pub/thunderbird/releases/")
                split_string = "<tr"
                ignore_lines_start = 4
            for release in content.split(split_string)[ignore_lines_start:]:
                try:
                    if package == "virtualbox":
                        version = release.split("HREF=\"")[1].split("/\"")[0]
                    else:
                        version = release.split("<a href=\"")[1].split("/\"")[0]
                    if version[0] in "0123456789" and not "b" in version and not "RC" in version and not "BETA" in version:
                        version_list.append(version)
                except:
                    pass
            version_list.sort(lambda a,b: cmp(LooseVersion(a), LooseVersion(b)))
            last_version = version_list[-1]
            
            if package in self._known_releases and LooseVersion(last_version) > LooseVersion(self._known_releases[package]):
                self._known_releases[package] = last_version
                if self._has_config("warn_users"):
                    warn_users = self._get_config("warn_users").split(",")
                    msg_start = ", ".join(warn_users) + " : "
                else:
                    msg_start = ""
                return self.privmsg_response(self._get_config("output_channel"), msg_start + "New upstream release of %s %s" % (package, last_version))
            else:
                self._known_releases[package] = last_version
        except:
            pass
