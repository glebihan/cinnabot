#! /usr/bin/python
# -*- coding=utf-8 -*-

from Cinnabot.BasePlugin import BasePlugin
import time
import urllib
import requests
import random

USE_DB = True
DB_UPGRADES = {
    1: [
        """CREATE TABLE IF NOT EXISTS `ignore_users` (
            `user_id`
        )"""
    ]
}

class CommunityRegistrationPlugin(BasePlugin):
    def __init__(self, bot, plugin_name):
        BasePlugin.__init__(self, bot, plugin_name)
        self._users_with_code = {}
        try:
            bot._irc.execute_every(int(self._get_config("change_code_delay")) * 3600, self._change_code)
        except:
            pass
    
    def _get_ignore_users(self):
        if not hasattr(self, '_ignore_users'):
            self._ignore_users = [i[0] for i in self._db_query("SELECT user_id FROM ignore_users")]
        return self._ignore_users
    ignore_users = property(_get_ignore_users)
    
    def add_ignore_user(self, username):
        self._db_query("INSERT INTO ignore_users (user_id) VALUES (?)", (username,))
        self._ignore_users.append(username)
    
    def _change_code(self):
        self._start_task(self._do_change_code)
    
    def _do_change_code(self):
        new_code = '-'.join([''.join(random.sample('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ', 4)) for i in range(4)])
        data = {'username': self._get_config("username") ,'password': self._get_config("password"), 'login': 'Login'}
        res = requests.post("https://community.linuxmint.com/auth/login", data = data, allow_redirects = False, verify = False)
        cookies = {}
        for i in res.cookies:
            cookies[i.name] = i.value
        data = {'search': "Change code", 'passcode': new_code}
        requests.post("https://community.linuxmint.com/user/change_registration_passcode", cookies = cookies, data = data, verify = False)
            
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
        res = requests.post("https://community.linuxmint.com/auth/login", data = data, allow_redirects = False, verify = False)
        cookies = {}
        for i in res.cookies:
            cookies[i.name] = i.value
        content = requests.get("https://community.linuxmint.com/user/moderators", cookies = cookies, verify = False).text
        
        search_str = "<input type=\"text\" name=\"passcode\" value=\""
        i = content.index(search_str)
        return content[i+len(search_str):].split('"')[0]
    
    def process_privmsg(self, from_username, source, target, msg):
        if msg.lower() in ["newcode", "new code"] and self._bot._is_semi_admin(source):
            self._change_code()
            return
            
        if from_username and msg.lower() in ["nomorecodes", "no more codes"] and not from_username in self.ignore_users:
            self.add_ignore_user(from_username)
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
            if from_nickname in self._bot._nick_to_username_map and self._bot._nick_to_username_map[from_nickname] in self.ignore_users:
                return
            if not source in self._users_with_code or ((time.time() - self._users_with_code[source]) > 300):
                self._users_with_code[source] = time.time()
                
                code = self._retrieve_code()
                
                return [self.notice_response(source.split("!")[0], "Your registration code is %s" % code), self.privmsg_response(target, "Code sent. Welcome to the community, %s!" % from_nickname)]
        
        if len(words) == 2 and words[0].lower() in ["!code", "!registration"]:
            dest_nickname = words[1]
            if not dest_nickname in self._users_with_code or ((time.time() - self._users_with_code[dest_nickname]) > 300):
                self._users_with_code[dest_nickname] = time.time()
                
                code = self._retrieve_code()
                
                return [self.notice_response(dest_nickname, "Your registration code is %s" % code), self.privmsg_response(target, "Code sent. Welcome to the community, %s!" % dest_nickname)]
