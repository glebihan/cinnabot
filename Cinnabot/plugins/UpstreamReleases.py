#! /usr/bin/python
# -*- coding=utf-8 -*-

from Cinnabot.BasePlugin import BasePlugin
import logging
import httplib2
import re
from distutils.version import LooseVersion

USE_DB = True
DB_UPGRADES = {
    1: [
        """CREATE TABLE IF NOT EXISTS `ignores` (
            `ignore_id` INTEGER PRIMARY KEY AUTOINCREMENT,
            `package` TEXT,
            `version` TEXT
        )"""
    ],
    2: [
        """ CREATE TABLE IF NOT EXISTS `pins` (
            `pin_id` INTEGER PRIMARY KEY AUTOINCREMENT,
            `target` TEXT,
            `package` TEXT,
            `username` TEXT
        )"""
    ],
    3: [
        """ CREATE TABLE IF NOT EXISTS `pins_ignores` (
            `ignore_id` INTEGER PRIMARY KEY AUTOINCREMENT,
            `package` TEXT,
            `version` TEXT,
            `username` TEXT
        )"""
    ]
}

IGNORE_COMMAND_RE = re.compile("^\\ *ignore\\ *([0-9a-z\-\.\_]+)\\ +([0-9\.\-a-z\:]+)\\ *$")
DEIGNORE_COMMAND_RE = re.compile("^\\ *deignore\\ *([0-9a-z\-\.\_]+)\\ +([0-9\.\-a-z\:\+~]+)\\ *$")
IGNORED_COMMAND_RE = re.compile("^\\ *ignored\\ *$")

ADD_PIN_COMMAND_RE = re.compile("^\\ *add\\ +pin\\ +([a-z]+)\\ +([0-9a-z\-\.\_]+)\\ *$")
IGNORE_PIN_COMMAND_RE = re.compile("^\\ *ignore\\ +pin\\ *([0-9a-z\-\.\_]+)\\ +([0-9\.\-a-z\:\+~]+)\\ *$")
DEIGNORE_PIN_COMMAND_RE = re.compile("^\\ *deignore\\ +pin\\ *([0-9a-z\-\.\_]+)\\ +([0-9\.\-a-z\:\+~]+)\\ *$")
PINS_COMMAND_RE = re.compile("^\\ *pins\\ *$")

class UpstreamReleasesPlugin(BasePlugin):
    def __init__(self, bot, plugin_name):
        BasePlugin.__init__(self, bot, plugin_name)
                
        bot._irc.execute_every(3600, self._check_releases)
        self._check_releases()
    
    def get_help(self):
        return {
            "ignore": {
                "syntax": "ignore <package> <version>",
                "description": "Ignore a specific upstream version of a package"
            },
            "deignore": {
                "syntax": "deignore <package> <version>",
                "description": "Stop ignoring a specific upstream version of a package"
            },
            "ignored": {
                "syntax": "ignored",
                "description": "List ignored upstream versions"
            },
            "add pin": {
                "syntax": "add pin <release> <package>",
                "description": "Receive notifications about versions of a given package in the repositories of the given Ubuntu release"
            },
            "ignore pin": {
                "syntax": "ignore pin <package> <version>",
                "description": "Don't receive notifications about a specific version of a package"
            },
            "deignore pin": {
                "syntax": "deignore pin <package> <version>",
                "description": "Cancels a previously used \"ignore pin\" command"
            },
            "pins": {
                "syntax": "pins",
                "description": "List pinned packages and ignored versions for those pins"
            }
        }
            
    def _check_releases(self):
        self._start_task(self._do_check_releases, "firefox")
        self._start_task(self._do_check_releases, "thunderbird")
        self._start_task(self._do_check_releases, "virtualbox")
        self._start_task(self._do_check_releases, "flash")
        #~ self._start_task(self._do_check_releases, "hplip")
        self._start_task(self._check_pin_releases)
    
    def _check_pin_releases(self):
        res = []
        
        c = httplib2.Http()
        for pin_id, target, package, username in self._db_query("SELECT * FROM `pins`"):
            ignored_versions = [i[0] for i in self._db_query("SELECT version FROM pins_ignores WHERE package = ? AND username = ?", (package, username))]
            last_version = None
            for url in ["http://packages.ubuntu.com/%s/%s" % (target, package), "http://packages.ubuntu.com/%s-updates/%s" % (target, package)]:
                try:
                    resp, content = c.request(url)
                    version = content.split('id="screenshot"')[1].split('img src="')[1].split('"')[0].split('/')[-1]
                    if last_version is None or LooseVersion(version) > LooseVersion(last_version):
                        last_version = version
                except:
                    pass
            if last_version is not None and not last_version in ignored_versions:
                res.append(self.privmsg_response(username, "New %s release of %s %s" % (target, package, last_version)))
        
        return res
    
    def _do_check_releases(self, package):
        ignore_versions = [v[2] for v in self._db_query("SELECT * FROM `ignores` WHERE `package` = ?", (package,))]
        version_list = []
        c = httplib2.Http()
        if package == "virtualbox":
            resp, content = c.request("http://download.virtualbox.org/virtualbox/")
            split_string = "<a"
            ignore_lines_start = 0
        elif package == "hplip":
            resp, content = c.request("http://sourceforge.net/projects/hplip/files/hplip/")
            split_string = "<th scope=\"row\" headers=\"files_name_h\">"
            ignore_lines_start = 1
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
                        version = release.split("href=\"")[1].split("/\"")[0]
                    else:
                        version = release.split("<a href=\"")[1].split("/\"")[0]
                    if package in ["hplip", "firefox", "thunderbird"]:
                        version = version.split("/")[-1]
                    if version[0] in "0123456789" and not "esr" in version and not "b" in version and not "RC" in version and not "BETA" in version and not "funnelcake" in version:
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
            version_list = []
            if package == "flash":
                mint_package = "mint-flashplugin-24"
            else:
                mint_package = package
            if package in ["firefox", "thunderbird"]:
                component = "upstream"
            else:
                component = "import"
            current_versions_link = "http://chicago.linuxmint.com/pool/%s/%s/%s/" % (component, mint_package[0], mint_package)
            resp, content = c.request(current_versions_link)
            for release in content.split("<a"):
                try:
                    filename = release.split("href=\"")[1].split("\"")[0]
                    if filename.endswith(".tar.gz"):
                        if package == "flash":
                            version_list.append(filename[len(mint_package) + 1:][:-7])
                        else:
                            version_list.append(filename[len(mint_package) + 1:].split("%")[0])
                except:
                    pass
            version_list.sort(lambda a,b: cmp(LooseVersion(a), LooseVersion(b)))
            current_version = version_list[-1]
        if current_version == None:
            raise Exception("Could not load current version for %s" % package)
        
        if last_version not in ignore_versions and LooseVersion(last_version) > LooseVersion(current_version):
            res = []
            warn_users = self._get_config("warn_users").split(",")
            for u in warn_users:
                res.append(self.privmsg_response(u, "New upstream release of %s %s" % (package, last_version)))
            return res
    
    def process_privmsg(self, from_username, source, target, msg):
        if from_username in self._get_config("warn_users").split(","):
            match = IGNORE_COMMAND_RE.match(msg)
            if match:
                self._db_query("INSERT INTO `ignores` (`package`, `version`) VALUES (?, ?)", match.groups())
            
            match = DEIGNORE_COMMAND_RE.match(msg)
            if match:
                self._db_query("DELETE FROM `ignores` WHERE `package` = ? AND `version` = ?", match.groups())
            
            match = IGNORED_COMMAND_RE.match(msg)
            if match:
                res = []
                for package, version in self._db_query("SELECT `package`, `version` FROM `ignores`"):
                    res.append(self.privmsg_response(source.split("!")[0], "%s %s" % (package, version)))
                return res
            
        match = PINS_COMMAND_RE.match(msg)
        if match:
            res = []
            res.append(self.privmsg_response(source.split("!")[0], "PINNED PACKAGES :"))
            for target, package in self._db_query("SELECT target, package FROM pins WHERE username = ?", (source.split('!')[0],)):
                res.append(self.privmsg_response(source.split("!")[0], "%s %s" % (target, package)))
            res.append(self.privmsg_response(source.split("!")[0], "IGNORED VERSIONS :"))
            for package, version in self._db_query("SELECT package, version FROM pins_ignores WHERE username = ? ORDER BY package ASC, ignore_id DESC", (source.split('!')[0],)):
                res.append(self.privmsg_response(source.split("!")[0], "%s %s" % (package, version)))
            return res
            
        match = ADD_PIN_COMMAND_RE.match(msg)
        if match:
            self._db_query("INSERT INTO `pins` (`target`, `package`, `username`) VALUES (?, ?, ?)", match.groups() + (source.split('!')[0],))
        
        match = IGNORE_PIN_COMMAND_RE.match(msg)
        if match:
            self._db_query("INSERT INTO `pins_ignores` (`package`, `version`, `username`) VALUES (?, ?, ?)", match.groups() + (source.split('!')[0],))

        match = DEIGNORE_PIN_COMMAND_RE.match(msg)
        if match:
            self._db_query("DELETE FROM `pins_ignores` WHERE `package` = ? AND `version` = ? AND `username` = ?", match.groups() + (source.split('!')[0],))
