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
        words = [w.replace("?", "").replace(".", "").rstrip().lstrip() for w in msg.split()]
        words_lower = [w.replace("!", "").lower() for w in words]
        
        if ("registration" in words_lower and "code" in words_lower) or ("community" in words_lower and "code" in words_lower) or ("registration" in words_lower and "community" in words_lower) or ("reg code" in msg.lower()):
            if not source in self._users_with_code or ((time.time() - self._users_with_code[source]) > 300):
                self._users_with_code[source] = time.time()
                
                code = self._retrieve_code()
                
                return [self.privmsg_response(source.split("!")[0], code), self.privmsg_response(target, source.split("!")[0] + ": Hi. I sent you a registration code via PM (check the tab with my name on it). Welcome to Linux Mint ;)")]
        
        if len(words) == 2 and words[0].lower() in ["!code", "!registration"]:
            dest_nickname = words[1]
            if not dest_nickname in self._users_with_code or ((time.time() - self._users_with_code[dest_nickname]) > 300):
                self._users_with_code[dest_nickname] = time.time()
                
                code = self._retrieve_code()
                
                return [self.privmsg_response(dest_nickname, code), self.privmsg_response(target, dest_nickname + ": Hi. I sent you a registration code via PM (check the tab with my name on it). Welcome to Linux Mint ;)")]
