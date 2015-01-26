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
        self._start_task(self._do_check_releases, "flash")
    
    def _do_check_releases(self, package):
        version_list = []
        c = httplib2.Http()
        if package == "virtualbox":
            resp, content = c.request("http://download.virtualbox.org/virtualbox/")
            split_string = "<A"
            ignore_lines_start = 0
        elif package == "flash":
            resp, content = c.request("https://www.adobe.com/software/flash/about/")
        elif package == "firefox":
            resp, content = c.request("https://download-installer.cdn.mozilla.net/pub/firefox/releases/")
            split_string = "<tr"
            ignore_lines_start = 4
        else:
            resp, content = c.request("https://download-installer.cdn.mozilla.net/pub/thunderbird/releases/")
            split_string = "<tr"
            ignore_lines_start = 4
        if package == "flash":
            version_list.append(content.split("<strong>Linux</strong>")[1].split('</tr>')[0].split('<td>')[-1].split('</td>')[0])
        else:
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
        if len(version_list) == 0:
            raise Exception("Could not load last version for %s" % package)
        version_list.sort(lambda a,b: cmp(LooseVersion(a), LooseVersion(b)))
        last_version = version_list[-1]
        if package == "firefox":
            resp, content = c.request("https://download-installer.cdn.mozilla.net/pub/firefox/releases/" + last_version)
            while "Thanks for your interest" in content:
                del version_list[-1]
                last_version = version_list[-1]
                resp, content = c.request("https://download-installer.cdn.mozilla.net/pub/firefox/releases/" + last_version)
        
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
            if package == "flash":
                mint_package = "mint-flashplugin-11"
            else:
                mint_package = package
            current_versions_link = "http://denver.linuxmint.com/pool/import/%s/%s/" % (mint_package[0], mint_package)
            resp, content = c.request(current_versions_link)
            for release in content.split("<a"):
                try:
                    filename = release.split("href=\"")[1].split("\"")[0]
                    if filename.endswith(".tar.gz"):
                        if package == "flash":
                            current_version = filename[len(mint_package) + 1:][:-7]
                        else:
                            current_version = filename[len(mint_package) + 1:].split("%")[0]
                except:
                    pass
        if current_version == None:
            raise Exception("Could not load current version for %s" % package)
        
        if LooseVersion(last_version) > LooseVersion(current_version):
            res = []
            warn_users = self._get_config("warn_users").split(",")
            for u in warn_users:
                res.append(self.privmsg_response(u, "New upstream release of %s %s" % (package, last_version)))
            return res
