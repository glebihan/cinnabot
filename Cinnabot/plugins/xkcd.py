#! /usr/bin/python
# -*- coding=utf-8 -*-

from Cinnabot.BasePlugin import BasePlugin
import urllib
import json
import re

REG_EXP = re.compile("xkcd\W*(\d+)", re.I)

class xkcdPlugin(BasePlugin):
    def _retrieve_info(self, url):
        try:
            filename, message = urllib.urlretrieve(url)
            f = open(filename)
            data = f.read()
            f.close()
            return json.loads(data)
        except:
            return None

    def _format_info(self, num, info):
        try:
            title = info["title"]
            if len(title) > 97:
                title = title[:97] + "..."

            return u"\x0314xkcd #%s [%s.%s.%s]\x0f: %s \x0302\x1f%s\x0f" % (num, info["day"], info["month"], info["year"], title, info["img"])
        except:
            return None

    def process_channel_message(self, source, target, msg):
        while u'\x03' in msg:
            i = msg.index(u'\x03')
            msg = msg[:i] + msg[i + 3:]
        msg = msg.replace("\x0f", "")
        match = REG_EXP.search(msg)

        if match:
            num = match.group(1)
            url = "http://xkcd.com/%s/info.0.json" % num
            info = self._retrieve_info(url)
            if info:
                output_message = self._format_info(num, info)
                if output_message:
                    return self.privmsg_response(target, output_message)
