#! /usr/bin/python
# -*- coding=utf-8 -*-

from Cinnabot.BasePlugin import BasePlugin
import logging
import httplib2
from distutils.version import LooseVersion

class UpstreamReleasesPlugin(BasePlugin):
    def __init__(self, bot, plugin_name):
        BasePlugin.__init__(self, bot, plugin_name)
                
        bot._irc.execute_every(3600, self._check_releases)
        self._check_releases()
    
    def _check_releases(self):
        self._start_task(self._do_check_releases, "firefox")
        self._start_task(self._do_check_releases, "thunderbird")
        self._start_task(self._do_check_releases, "virtualbox")
    
    def _do_check_releases(self, package):
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
        
        current_version = None
        
        if package == "virtualbox":
            main_version = None
            resp, content = c.request("http://extra.linuxmint.com/pool/main/v/")
            for p in content.split("<a"):
                try:
                    link = p.split("href=\"")[1].split("/\"")[0]
                    if link.startswith("virtualbox-"):
                        version = link.split("-")[-1]
                        if main_version == None or LooseVersion(version) > LooseVersion(main_version):
                            main_version = version
                except:
                    pass
            current_versions_link = "http://extra.linuxmint.com/pool/main/v/virtualbox-%s/" % main_version
            resp, content = c.request(current_versions_link)
            for release in content.split("<a"):
                try:
                    filename = release.split("href=\"")[1].split("\"")[0]
                    v = filename.split("_")[1].split("-")[0]
                    if current_version == None or LooseVersion(v) > LooseVersion(current_version):
                        current_version = v
                except:
                    pass
        else:
            current_versions_link = "http://packages.linuxmint.com/pool/import/%s/%s/" % (package[0], package)
            resp, content = c.request(current_versions_link)
            for release in content.split("<a"):
                try:
                    filename = release.split("href=\"")[1].split("\"")[0]
                    if filename.endswith(".tar.gz"):
                        current_version = filename[len(package) + 1:].split("%")[0]
                except:
                    pass
        
        if LooseVersion(last_version) > LooseVersion(current_version):
            res = []
            warn_users = self._get_config("warn_users").split(",")
            for u in warn_users:
                res.append(self.privmsg_response(u, "New upstream release of %s %s" % (package, last_version)))
            return res
