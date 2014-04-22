#! /usr/bin/python
# -*- coding=utf-8 -*-

from Cinnabot.BasePlugin import BasePlugin
import re
import httplib2

REG_EXP = re.compile("^\\ *build\\ +([a-z\-]+)\\ *(on\\ +([a-z]+))?\\ *$")

class EasyLRHPlugin(BasePlugin):
    def process_highlight(self, from_username, source, target, msg):
        match = REG_EXP.match(msg)
        if match:
            package, ig, distro_code = match.groups()
            url = "http://easy-lrh.gwendallebihan.net/trigger_build?package=" + package
            if distro_code:
                url += "&target=" + distro_code
            c = httplib2.Http()
            c.add_credentials(self._get_config("easylrh_username"), self._get_config("easylrh_password"))
            resp, content = c.request(url)
            if target.startswith("#"):
                resp_target = target
            else:
                resp_target = source.split("!")[0]
            return self.privmsg_response(resp_target, content)
    
    def process_privmsg(self, from_username, source, target, msg):
        return self.process_highlight(from_username, source, target, msg)
