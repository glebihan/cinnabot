#! /usr/bin/python
# -*- coding=utf-8 -*-

from Cinnabot.BasePlugin import BasePlugin
import time
import urllib
import requests
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
        data = {'username': self._get_config("username") ,'password': self._get_config("password"), 'login': 'Login'}
        content = requests.post("https://community.linuxmint.com/auth/login", headers = {'Content-type' : 'application/x-www-form-urlencoded'}, data = data).text
        data = {'search': "Change code", 'passcode': new_code}
        requests.post("https://community.linuxmint.com/user/change_registration_passcode", headers = {'Content-type' : 'application/x-www-form-urlencoded', 'Cookie' : resp["set-cookie"]}, data = data)
            
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
        data = {'username': self._get_config("username") ,'password': self._get_config("password"), 'login': 'Login'}
        res = requests.post("https://community.linuxmint.com/auth/login", data = data, allow_redirects = False)
        content = requests.get("https://community.linuxmint.com/user/moderators", cookies = {"ci_session": res.cookies["ci_session"], "sucuric_prtmpcb": res.cookies["sucuric_prtmpcb"]}).text
        
        search_str = "<input type=\"text\" name=\"passcode\" value=\""
        i = content.index(search_str)
        return content[i+len(search_str):].split('"')[0]
    
    def process_privmsg(self, from_username, source, target, msg):
        if msg.lower() in ["newcode", "new code"] and self._bot._is_semi_admin(source):
            self._change_code()
            return
            
        if from_username and msg.lower() in ["nomorecodes", "no more codes"] and not from_username in self._ignore_users:
            self._ignore_users.append(from_username)
            self._set_config("ignore_users", ",".join(self._ignore_users))
            return self.privmsg_response(source.split("!")[0], "OK, I won't send you registration codes anymore")
        
    def process_channel_message(self, source, target, msg):
        words = msg.replace("'", "").replace('"', "").split()

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
        
        if (("denregistrement" in words_lower or "enregistrement" in words_lower) and "code" in words_lower) or ("registro" in words_lower and (u'c\ufffddigo' in words_lower or 'codigo' in words_lower)) or ("registration" in words_lower and "code" in words_lower) or ("community" in words_lower and "code" in words_lower) or ("registration" in words_lower and "community" in words_lower) or ("reg code" in msg.lower()) or ("reg. code" in msg.lower()):
            from_nickname = source.split("!")[0]
            if from_nickname in self._bot._nick_to_username_map and self._bot._nick_to_username_map[from_nickname] in self._ignore_users:
                return
            if not source in self._users_with_code or ((time.time() - self._users_with_code[source]) > 300):
                self._users_with_code[source] = time.time()
                
                code = self._retrieve_code()
                
                return [self.notice_response(source.split("!")[0], "Your registration code is %s" % code), self.privmsg_response(target, "Code sent")]
        
        if len(words) == 2 and words[0].lower() in ["!code", "!registration"]:
            dest_nickname = words[1]
            if not dest_nickname in self._users_with_code or ((time.time() - self._users_with_code[dest_nickname]) > 300):
                self._users_with_code[dest_nickname] = time.time()
                
                code = self._retrieve_code()
                
                return [self.notice_response(dest_nickname, "Your registration code is %s" % code), self.privmsg_response(target, "Code sent")]
