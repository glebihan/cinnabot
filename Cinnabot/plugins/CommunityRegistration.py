#! /usr/bin/python
# -*- coding=utf-8 -*-

from Cinnabot.BasePlugin import BasePlugin
import time
import urllib
import httplib2

class CommunityRegistrationPlugin(BasePlugin):
    def __init__(self, bot, plugin_name):
        BasePlugin.__init__(self, bot, plugin_name)
        self._users_with_code = {}
            
    def get_cookies_str(self, cookies):
        cookies_array = []
        for key in cookies.keys():
            cookies_array.append(key + "=" + cookies[key])
        return ";".join(cookies_array)
   
    def parse_cookies(self, cookies):
        cookies_array = {}
        for i in cookies.split(","):
            cookie = i.split(";")[0].rstrip().lstrip()
            if "=" in cookie:
                key, value = cookie.split("=")
                cookies_array[key] = value
        return cookies_array
    
    def _retrieve_code(self):
        http = httplib2.Http()
        data = urllib.urlencode({'username': self._get_config("username") ,'password': self._get_config("password"), 'login': 'Login'})
        resp, content = http.request("http://community.linuxmint.com/auth/login", "POST", headers = {'Content-type' : 'application/x-www-form-urlencoded'}, body = data)
        resp, content = http.request("http://community.linuxmint.com/user/moderators", "GET", headers = {'Cookie' : resp["set-cookie"]})
        
        search_str = "<input type=\"text\" name=\"passcode\" value=\""
        i = content.index(search_str)
        return content[i+len(search_str):].split('"')[0]
        
    def process_channel_message(self, source, target, msg):
        words = [w.replace("?", "").replace(".", "").replace("!", "").rstrip().lstrip().lower() for w in msg.split()]
        
        if ("registration" in words and "code" in words) or ("community" in words and "code" in words) or ("registration" in words and "community" in words):
            if not source in self._users_with_code or ((time.time() - self._users_with_code[source]) > 10):
                self._users_with_code[source] = time.time()
                
                code = self._retrieve_code()
                
                return [self.privmsg_response(source.split("!")[0], code), self.privmsg_response(target, source.split("!")[0] + ", see private message for registration code")]
