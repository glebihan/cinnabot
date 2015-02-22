#! /usr/bin/python
# -*- coding=utf-8 -*-

from Cinnabot.BasePlugin import BasePlugin
import time
import urllib
import httplib2
import random

class CommunityRegistrationPlugin(BasePlugin):
    def __init__(self, bot, plugin_name):
        BasePlugin.__init__(self, bot, plugin_name)
        self._users_with_code = {}
        if self._has_config("ignore_users"):
            self._ignore_users = self._get_config("ignore_users").split(",")
        else:
            self._ignore_users = []
        
        try:
            bot._irc.execute_every(int(self._get_config("change_code_delay")) * 3600, self._change_code)
        except:
            pass
    
    def _change_code(self):
        self._start_task(self._do_change_code)
    
    def _do_change_code(self):
        new_code = '-'.join([''.join(random.sample('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ', 4)) for i in range(4)])
        http = httplib2.Http()
        data = urllib.urlencode({'username': self._get_config("username") ,'password': self._get_config("password"), 'login': 'Login'})
        resp, content = http.request("http://community.linuxmint.com/auth/login", "POST", headers = {'Content-type' : 'application/x-www-form-urlencoded'}, body = data)
        data = urllib.urlencode({'search': "Change code", 'passcode': new_code})
        http.request("http://community.linuxmint.com/user/change_registration_passcode", "POST", headers = {'Content-type' : 'application/x-www-form-urlencoded', 'Cookie' : resp["set-cookie"]}, body = data)
            
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
    
    def process_privmsg(self, from_username, source, target, msg):
        if from_username and msg.lower() in ["nomorecodes", "no more codes"] and not from_username in self._ignore_users:
            self._ignore_users.append(from_username)
            self._set_config("ignore_users", ",".join(self._ignore_users))
            return self.privmsg_response(source.split("!")[0], "OK, I won't send you registration codes anymore")
        
    def process_channel_message(self, source, target, msg):
        from_nickname = source.split("!")[0]
        if from_nickname in self._bot._nick_to_username_map and self._bot._nick_to_username_map[from_nickname] in self._ignore_users:
            return
            
        words = msg.split()

        current_word = ""
        words_lower = []
        for i in msg.lower():
            if i in ",;:?.! ()":
                if current_word != "":
                    words_lower.append(current_word)
                    current_word = ""
            else:
                current_word += i
        if current_word != "":
            words_lower.append(current_word)
        
        if ("d'enregistrement" in words_lower and "code" in words_lower) or ("registro" in words_lower and (u'c\ufffddigo' in words_lower or 'codigo' in words_lower)) or ("registration" in words_lower and "code" in words_lower) or ("community" in words_lower and "code" in words_lower) or ("registration" in words_lower and "community" in words_lower) or ("reg code" in msg.lower()) or ("reg. code" in msg.lower()):
            if not source in self._users_with_code or ((time.time() - self._users_with_code[source]) > 300):
                self._users_with_code[source] = time.time()
                
                code = self._retrieve_code()
                
                return [self.privmsg_response(source.split("!")[0], code), self.privmsg_response(target, source.split("!")[0] + ": Hi. I sent you a registration code via private message (check the tab with my name on it). Welcome to Linux Mint ;)")]
        
        if len(words) == 2 and words[0].lower() in ["!code", "!registration"]:
            dest_nickname = words[1]
            if not dest_nickname in self._users_with_code or ((time.time() - self._users_with_code[dest_nickname]) > 300):
                self._users_with_code[dest_nickname] = time.time()
                
                code = self._retrieve_code()
                
                return [self.privmsg_response(dest_nickname, code), self.privmsg_response(target, dest_nickname + ": Hi. I sent you a registration code via private message (check the tab with my name on it). Welcome to Linux Mint ;)")]
