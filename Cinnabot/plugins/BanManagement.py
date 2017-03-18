#! /usr/bin/python
# -*- coding=utf-8 -*-

from Cinnabot.BasePlugin import BasePlugin
import logging
import re
import datetime
import requests

CHANNEL_FLAGS_RE = re.compile("^[0-9]+\ +(\!?[a-zA-Z0-9_\[\]\|\^\`\-]+)\ +\+([a-zA-Z]+)\ +\(\#([a-zA-Z0-9\\-\\_]+)\).*$")
GROUPS_FLAGS_RE = re.compile("^[0-9]+\ +([a-zA-Z0-9_\[\]\|\^\`\-]+)\ +\+([a-zA-Z]+)$")
END_GROUPS_FLAGS_RE = re.compile("^End of (\![a-zA-Z0-9_\[\]\|\^\`\-]+) FLAGS listing.$")

USE_DB = True
DB_UPGRADES = {
    1: [
        """CREATE TABLE IF NOT EXISTS `bans` (
            `ban_id` INTEGER PRIMARY KEY AUTOINCREMENT,
            `mask` TEXT,
            `nickname` TEXT,
            `channel` TEXT,
            `from_op` TEXT,
            `ban_date` DATETIME,
            `ban_expiration` DATETIME,
            `comment` TEXT,
            `removed` BOOLEAN
        )"""
    ],
    2: [
        """CREATE TABLE IF NOT EXISTS `kick_history` (
            `kick_id` INTEGER PRIMARY KEY AUTOINCREMENT,
            `mask` TEXT,
            `nickname` TEXT,
            `channel` TEXT,
            `from_op` TEXT,
            `date` TEXT,
            `comment` TEXT
        )"""
    ],
    3: [
        """CREATE TABLE IF NOT EXISTS `badwords` (
            `badword` TEXT
        )"""
    ]
}

class BanManagementPlugin(BasePlugin):
    def __init__(self, bot, plugin_name):
        BasePlugin.__init__(self, bot, plugin_name)
        
        self._bot._irc.add_global_handler("privnotice", self._on_irc_notice)
        
        self._channels = self._get_config("channels").split(",")
        self._current_loading_group = None
        self._load_operators_flags()
        
        bot._irc.execute_every(900, self._load_operators_flags)
        bot._irc.execute_every(60, self._check_expired_bans)
    
    def get_help(self):
        return {
            "add badword": {
                "syntax": "add badword <badword>",
                "description": "Add a bad word to the list"
            },
            "remove badword": {
                "syntax": "remove badword <badword>",
                "description": "Remove a bad word from the list"
            },
            "list badword": {
                "syntax": "list badword",
                "description": "Show list of words identified as bad words"
            }
        }
    
    def _load_operator_groups(self):
        if self._current_loading_group:
            return
        for i in self._operators_groups:
            if self._operators_groups[i] == None:
                self._operators_groups[i] = []
                self._current_loading_group = i
                self._bot._irc_server_connection.privmsg("GroupServ", "flags %s" % i)
                return
    
    def _on_irc_notice(self, server_connection, event):
        logging.info("BanManagementPlugin::_on_irc_notice:" + event.source + ":" + event.target + ":" + event.type + ":" + str(event.arguments))

        match = CHANNEL_FLAGS_RE.match(event.arguments[0])
        if match:
            username, flags, channel = match.groups()
            if "o" in flags or "O" in flags or "h" in flags or "H" in flags:
                self._operators.setdefault("#" + channel, []).append(username)
        for channel in self._operators:
            for username in self._operators[channel]:
                if username.startswith("!") and not username in self._operators_groups:
                    self._operators_groups[username] = None
                    self._load_operator_groups()
        
        match = GROUPS_FLAGS_RE.match(event.arguments[0])
        if match:
            username, flags = match.groups()
            self._operators_groups[self._current_loading_group].append(username)
            
        match = END_GROUPS_FLAGS_RE.match(event.arguments[0])
        if match:
            group = match.groups()[0]
            for i in self._operators:
                if group in self._operators[i]:
                    self._operators[i] += self._operators_groups[group]
            self._current_loading_group = None
            self._load_operator_groups()
            
    def _load_operators_flags(self):
        self._operators = {}
        self._operators_groups = {}
        for i in self._channels:
            self._bot._irc_server_connection.privmsg("ChanServ", "flags %s" % i)
    
    def _get_badwords(self):
        if not hasattr(self, '_badwords'):
            self._badwords = [i[0].lower() for i in self._db_query("SELECT * FROM `badwords`")]
        return self._badwords
    badwords = property(_get_badwords)
        
    def process_channel_message(self, source, target, msg):
        self._bot._identify_user(source, self._on_channel_message_user_identified, source, target, msg)
        
        autoban_from_mask = self._get_config('autoban_from_mask')
        
        youtube_url = None
        youtube_match = re.search("""(https://www\.youtube\.com/watch\?v=\w+)""", msg)
        if youtube_match:
            youtube_groups = youtube_match.groups()
            youtube_url = youtube_groups[0]
        
        words = [i.lower() for i in re.split("\W+", msg)]
        
        for badword in self.badwords:
            if badword in words:
                for channel in self._channels:
                    self._on_channel_message_user_identified(autoban_from_mask.split('!')[0], autoban_from_mask, channel, '!kickban ' + source.split('!')[0])
                if youtube_url:
                    try:
                        new_badword = re.match("""^https://www\.youtube\.com/watch\?v=(\w+)$""", youtube_url).groups()[0]
                        self._db_query("INSERT INTO `badwords` VALUES (?)", [new_badword.lower()])
                        if hasattr(self, '_badwords'):
                            delattr(self, '_badwords')
                    except:
                        pass
                return
        
        words = []
        try:
            if youtube_url:
                youtube_data = requests.get(youtube_url).text
                for w in re.findall("""<meta property="og:video:tag" content="(.+)">""", youtube_data):
                    words += [i.lower() for i in re.split("\W+", w)]
                for w in re.findall("""<meta property="og:title" content="(.+)">""", youtube_data):
                    words += [i.lower() for i in re.split("\W+", w)]
        except:
            pass
        
        for badword in self.badwords:
            if badword in words:
                for channel in self._channels:
                    self._on_channel_message_user_identified(autoban_from_mask.split('!')[0], autoban_from_mask, channel, '!kickban ' + source.split('!')[0])
                if youtube_url:
                    try:
                        new_badword = re.match("""^https://www\.youtube\.com/watch\?v=(\w+)$""", youtube_url).groups()[0]
                        self._db_query("INSERT INTO `badwords` VALUES (?)", [new_badword.lower()])
                        if hasattr(self, '_badwords'):
                            delattr(self, '_badwords')
                    except:
                        pass
                return
    
    def _kick(self, mask, nickname, channel, from_op, comment):
        self._db_query("""
            INSERT INTO `kick_history` (`mask`, `nickname`, `channel`, `from_op`, `date`, `comment`)
            VALUES (?, ?, ?, ?, ?, ?)""", (mask, nickname, channel, from_op, datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), comment))
        return [self.kick_response(nickname, channel, comment)]
    
    def _ban(self, mask, nickname, channel, from_op, duration, comment):
        if duration == "f":
            endtime = None
        else:
            duration = duration.rstrip().lstrip()
            value = duration[:-1]
            unit = duration[-1]
            if unit == "m":
                endtime = datetime.datetime.utcnow() + datetime.timedelta(0, 0, 0, 0, int(value))
            elif unit == "h":
                endtime = datetime.datetime.utcnow() + datetime.timedelta(0, 0, 0, 0, 0, int(value))
            elif unit == "d":
                endtime = datetime.datetime.utcnow() + datetime.timedelta(int(value))
            endtime = endtime.strftime("%Y-%m-%d %H:%M:%S")
        self._db_query("UPDATE `bans` SET `removed` = 1 WHERE `channel` = ? AND `mask` = ?", (channel, mask))
        self._db_query("""
            INSERT INTO `bans` (`mask`, `nickname`, `channel`, `from_op`, `ban_date`, `ban_expiration`, `comment`, `removed`)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0)""", (mask, nickname, channel, from_op, datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), endtime, comment))
        return [self.ban_response(mask, channel)]
    
    def _unban(self, mask, channel):
        self._db_query("UPDATE `bans` SET `removed` = 1 WHERE `channel` = ? AND `mask` = ?", (channel, mask))
        return [self.unban_response(mask, channel)]
    
    def _on_hostmask(self, hostmask, keep_mask, command, from_op, channel, duration, comment, source):
        nickname = hostmask.split("!")[0]
        if keep_mask:
            ban_mask = hostmask
        else:
            ban_mask = "*!*@" + hostmask.split("@")[1]
        if command in ["!kick", "!kickban"]:
            self._start_task(self._kick, ban_mask, nickname, channel, from_op, comment)
        if command in ["!ban", "!kickban"]:
            self._start_task(self._ban, ban_mask, nickname, channel, from_op, duration, comment)
        if command in ["!unban"]:
            self._start_task(self._unban, ban_mask, channel)
        if command in ["!mute"]:
            self._start_task(self._ban, "m:" + ban_mask, nickname, channel, from_op, duration, comment)
        if command in ["!unmute"]:
            self._start_task(self._unban, "m:" + ban_mask, channel)
        if command in ["!history"]:
            self._start_task(self._history, source, nickname, ban_mask)
        
    def _banlist(self, from_op, channel):
        res = []
        for ban in self._db_query("SELECT * FROM `bans` WHERE `removed` = 0 AND `channel` = ?", (channel,)):
            res.append(self.notice_response(from_op.split("!")[0], "%s Banlist: \x0303%s UTC -> %s UTC\x0f \x0305%s %s\x0f (%s)" % (channel, ban[5], ban[6], ban[1], ban[4], ban[7])))
        res.append(self.notice_response(from_op.split("!")[0], "%s :End of channel ban list" % (channel,)))
        return res
    
    def _history(self, source, nickname, mask):
        bans = self._db_query("SELECT * FROM `bans` WHERE `mask` = ? OR `mask` = ? OR `nickname` = ?", (mask, "m:" + mask, nickname))
        kicks = self._db_query("SELECT * FROM `kick_history` WHERE `mask` = ? OR `nickname` = ?", (mask, nickname))
        res = []
        max_len_nick = 4
        max_len_mask = 4
        max_len_from_op = 8
        max_len_channel = 7
        for i in bans:
            max_len_nick = max(max_len_nick, len(i[2]))
            max_len_mask = max(max_len_mask, len(i[1]))
            max_len_from_op = max(max_len_from_op, len(i[4]))
            max_len_channel = max(max_len_channel, len(i[3]))
            res.append({"type": "ban", "nick": i[2], "mask": i[1], "from_op": i[4], "date": i[5], "expiration": i[6], "comment": i[7], "channel": i[3]})
        for i in kicks:
            max_len_nick = max(max_len_nick, len(i[2]))
            max_len_mask = max(max_len_mask, len(i[1]))
            max_len_from_op = max(max_len_from_op, len(i[4]))
            max_len_channel = max(max_len_channel, len(i[3]))
            res.append({"type": "kick", "nick": i[2], "mask": i[1], "from_op": i[4], "date": i[5], "expiration": " "*len(i[5]), "comment": i[6], "channel": i[3]})
        res.sort(lambda a,b: -cmp(a['date'], b['date']))
        final_res = [self.notice_response(source.split("!")[0], "%-*s   %-*s   %-*s   %-*s   %-*s   %s   %s   %s" % (5, "TYPE", max_len_channel + 1, "CHANNEL", max_len_nick + 1, "NICK", max_len_mask + 1, "MASK", max_len_from_op + 1, "OPERATOR", "DATE", "EXPIRATION", "COMMENT"))]
        for i in res:
            final_res.append(self.notice_response(source.split("!")[0], "%-*s   %-*s   %-*s   %-*s   %-*s   %s   %s   %s" % (5, i["type"], max_len_channel + 1, i["channel"], max_len_nick + 1, i["nick"], max_len_mask + 1, i["mask"], max_len_from_op + 1, i["from_op"], i["date"], i["expiration"], i["comment"])))
        return final_res
    
    def _on_channel_message_user_identified(self, username, source, target, msg):
        if username and username in self._operators.setdefault(target, []):
            while "  " in msg:
                msg = msg.replace("  ", " ")
            msg = msg.strip()
            words = msg.split()
            words[0] = words[0].lower()
            
            if words[0] in ["!kick", "!ban", "!kickban", "!unban", "!mute", "!unmute", "!history"]:
                nickname_or_mask = words[1]
                comment = ""
                duration = "1d"
                if words[0] != "!history":
                    if len(words) > 2:
                        if words[0] == "!kick":
                            comment = " ".join(words[2:])
                        else:
                            duration = words[2]
                    if len(words) > 3 and words[0] != "!kick":
                        comment = " ".join(words[3:])
                
                if "@" in nickname_or_mask:
                    self._on_hostmask(nickname_or_mask, True, words[0], username, target, duration, comment, source)
                else:
                    self._bot._get_user_hostmask(nickname_or_mask, self._on_hostmask, False, words[0], username, target, duration, comment, source)
            
            if words[0] == "!banlist":
                self._start_task(self._banlist, source, target)
    
    def _check_expired_bans(self):
        for ban in self._db_query("SELECT * FROM `bans` WHERE `removed` = 0 AND `ban_expiration` != '' AND `ban_expiration` IS NOT NULL AND `ban_expiration` < ?", (str(datetime.datetime.utcnow()),)):
            self._start_task(self._unban, ban[1], ban[3])
            self._db_query("UPDATE `bans` SET `removed` = 1 WHERE ban_id = ?", (ban[0],))
    
    def process_irc_ban(self, source, channel, mask):
        if not self._db_query("SELECT * FROM `bans` WHERE `channel` = ? AND `mask` = ? AND removed = 0", (channel, mask)):
            self._db_query("""
                INSERT INTO `bans` (`mask`, `nickname`, `channel`, `from_op`, `ban_date`, `ban_expiration`, `comment`, `removed`)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0)""", (mask, "", channel, source.split("!")[0], datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), (datetime.datetime.utcnow() + datetime.timedelta(1)).strftime("%Y-%m-%d %H:%M:%S"), ""))
    
    def process_irc_kick(self, source, channel, nickname, comment):
        if source.split("!")[0] != self._bot._irc_server_connection.get_nickname():
            self._bot._get_user_hostmask(nickname, self._on_hostmask, False, "!kick", source.split("!")[0], channel, "1d", comment, source)
        
    def process_irc_unban(self, source, channel, mask):
        self._db_query("UPDATE `bans` SET removed = 1 WHERE `channel` = ? AND `mask` = ?", (channel, mask))
    
    def process_privmsg(self, from_username, source, target, msg):
        self._bot._identify_user(source, self._on_privmsg_user_identified, source, target, msg)
    
    def _send_badwords(self, username, source, target, msg):
        badwords = self.badwords
        badwords.sort()
        res = []
        while len(badwords) > 0:
            wordsslice = badwords[:15]
            badwords = badwords[15:]
            res.append(self.privmsg_response(username, ', '.join(wordsslice)))
        return res
    
    def _on_privmsg_user_identified(self, username, source, target, msg):
        while "  " in msg:
            msg = msg.replace("  ", " ")
        msg = msg.strip()
        words = msg.split()
        words[0] = words[0].lower()
        if username and words[0] == "banlist" and username in self._operators.setdefault(words[1], []):
            self._start_task(self._banlist, source, words[1])
        all_operators = []
        for i in self._operators:
            all_operators += self._operators[i]
        if username and words[0] == "history" and username in all_operators:
            if "@" in words[1]:
                self._on_hostmask(words[1], True, words[0], username, target, "1d", "", source)
            else:
                self._bot._get_user_hostmask(words[1], self._on_hostmask, False, "!" + words[0], username, target, "1d", "", source)
        
        if username and words[0] in ["add", "remove", "list"] and words[1] == "badword" and username in all_operators:
            if words[0] in ["add", "remove"]:
                for word in words[2:]:
                    if words[0] == 'add':
                        self._db_query("INSERT INTO `badwords` VALUES (?)", [word.lower()])
                    else:
                        self._db_query("DELETE FROM `badwords` WHERE `badword` = ?", [word.lower()])
                if hasattr(self, '_badwords'):
                    delattr(self, '_badwords')
            else:
                self._start_task(self._send_badwords, username, source, target, msg)
