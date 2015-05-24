#! /usr/bin/python
# -*- coding=utf-8 -*-

from Cinnabot.BasePlugin import BasePlugin
import re
import httplib2
import urlparse
import fnmatch
from lxml.html import html5parser

REG_EXP = re.compile("^((([A-Za-z]{3,9}:(?:\/\/)?)(?:[\-;:&=\+\$,\w]+@)?[A-Za-z0-9\.\-]+|(?:www\.|[\-;:&=\+\$,\w]+@)[A-Za-z0-9\.\-]+)((?:\/[\+~%\/\.\w\-_]*)?\??(?:[\-\+=&;%@\.\w_]*)#?(?:[\.\!\/\\\w]*))?)$")

ADMIN_COMMANDS_RE = {
    "^\\ *url\\ whitelist\\ *$": "_show_whitelist",
    "^\\ *url\\ whitelist\\ add ([a-zA-Z\.\-\*]+)\\ *$": "_whitelist_add",
    "^\\ *url\\ whitelist\\ remove ([a-zA-Z\.\-\*]+)\\ *$": "_whitelist_remove"
}

class UrlsPlugin(BasePlugin):
    def _get_domains(self):
        if not hasattr(self, "_domains"):
            config_options = self._get_config_options()
            self._domains = []
            i = 1
            while "domain%d" % i in config_options:
                self._domains.append(self._get_config("domain%d" % i))
                i += 1
        return self._domains
    def _set_domains(self, domains):
        config_options = self._get_config_options()
        for i in config_options:
            if i.startswith("domain"):
                self._remove_config(i)
        self._domains = domains
        for i in range(len(self._domains)):
            self._set_config("domain%d" % (i + 1), self._domains[i])
    domains = property(_get_domains, _set_domains)
    
    def _get_admin_usernames(self):
        if "admin_usernames" in self._get_config_options():
            return self._get_config("admin_usernames").split(",")
        else:
            return []
    admin_usernames = property(_get_admin_usernames)
    
    def process_channel_message(self, source, target, msg):
        res = []
        c = httplib2.Http()
        for word in msg.split(" "):
            try:
                match = REG_EXP.match(word)
                if match:
                    url = match.groups()[0]
                    process = False
                    for domain in self.domains:
                        if fnmatch.fnmatch(urlparse.urlparse(url).netloc, domain):
                            process = True
                            break
                    if process:
                        resp, content = c.request(url)
                        tree = html5parser.fromstring(str(content))
                        for element in tree.iter("{http://www.w3.org/1999/xhtml}title"):
                            res.append(self.privmsg_response(target, "%s - \x0302\x1f%s\x0f" % (element.text, url)))
            except:
                pass
        return res
    
    def process_highlight(self, from_username, source, target, msg):
        if from_username in self.admin_usernames:
            for regexp in ADMIN_COMMANDS_RE:
                match = re.compile(regexp).match(msg)
                if match:
                    return getattr(self, ADMIN_COMMANDS_RE[regexp])(*((from_username,) + match.groups()))
    
    def process_privmsg(self, from_username, source, target, msg):
        return self.process_highlight(from_username, source, target, msg)
    
    def _show_whitelist(self, from_username):
        res = []
        for i in self.domains:
            res.append(self.notice_response(from_username, i))
        return res
    
    def _whitelist_add(self, from_username, domain):
        self.domains = self.domains + [domain]
    
    def _whitelist_remove(self, from_username, domain):
        domains = self.domains
        while domain in domains:
            i = domains.index(domain)
            del domains[i]
        self.domains = domains
