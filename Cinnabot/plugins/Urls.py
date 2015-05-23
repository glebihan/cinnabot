#! /usr/bin/python
# -*- coding=utf-8 -*-

from Cinnabot.BasePlugin import BasePlugin
import re
import httplib2
import urlparse
import fnmatch
from lxml.html import html5parser

REG_EXP = re.compile("^((([A-Za-z]{3,9}:(?:\/\/)?)(?:[\-;:&=\+\$,\w]+@)?[A-Za-z0-9\.\-]+|(?:www\.|[\-;:&=\+\$,\w]+@)[A-Za-z0-9\.\-]+)((?:\/[\+~%\/\.\w\-_]*)?\??(?:[\-\+=&;%@\.\w_]*)#?(?:[\.\!\/\\\w]*))?)$")

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
    domains = property(_get_domains)
    
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
