#! /usr/bin/python
# -*- coding=utf-8 -*-

from Cinnabot.BasePlugin import BasePlugin
import logging
import re
import datetime

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
            if "o" in flags or "O" in flags:
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
        
    def process_channel_message(self, source, target, msg):
        self._bot._identify_user(source, self._on_channel_message_user_identified, source, target, msg)
    
    def _kick(self, nickname, channel, comment):
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
    
    def _on_hostmask(self, hostmask, keep_mask, command, from_op, channel, duration, comment):
        nickname = hostmask.split("!")[0]
        if keep_mask:
            ban_mask = hostmask
        else:
            ban_mask = "*!*@" + hostmask.split("@")[1]
        if command in ["!kick", "!kickban"]:
            self._start_task(self._kick, nickname, channel, comment)
        if command in ["!ban", "!kickban"]:
            self._start_task(self._ban, ban_mask, nickname, channel, from_op, duration, comment)
        if command in ["!unban"]:
            self._start_task(self._unban, ban_mask, channel)
        if command in ["!mute"]:
            self._start_task(self._ban, "m:" + ban_mask, nickname, channel, from_op, duration, comment)
        if command in ["!unmute"]:
            self._start_task(self._unban, "m:" + ban_mask, channel)
        
    def _banlist(self, from_op, channel):
        res = []
        for ban in self._db_query("SELECT * FROM `bans` WHERE `removed` = 0 AND `channel` = ?", (channel,)):
            res.append(self.notice_response(from_op.split("!")[0], "%s Banlist: \x0303%s UTC -> %s UTC\x0f \x0305%s %s\x0f (%s)" % (channel, ban[5], ban[6], ban[1], ban[4], ban[7])))
        res.append(self.notice_response(from_op.split("!")[0], "%s :End of channel ban list" % (channel,)))
        return res
    
    def _on_channel_message_user_identified(self, username, source, target, msg):
        if username and username in self._operators.setdefault(target, []):
            while "  " in msg:
                msg = msg.replace("  ", " ")
            msg = msg.strip()
            words = msg.split()
            words[0] = words[0].lower()
            
            if words[0] in ["!kick", "!ban", "!kickban", "!unban", "!mute", "!unmute"]:
                nickname_or_mask = words[1]
                comment = ""
                duration = "1d"
                if len(words) > 2:
                    if words[0] == "!kick":
                        comment = " ".join(words[2:])
                    else:
                        duration = words[2]
                if len(words) > 3 and words[0] != "!kick":
                    comment = " ".join(words[3:])
                
                if "@" in nickname_or_mask:
                    self._on_hostmask(nickname_or_mask, True, words[0], username, target, duration, comment)
                else:
                    self._bot._get_user_hostmask(nickname_or_mask, self._on_hostmask, False, words[0], username, target, duration, comment)
            
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
    
    def process_irc_unban(self, source, channel, mask):
        self._db_query("UPDATE `bans` SET removed = 1 WHERE `channel` = ? AND `mask` = ?", (channel, mask))
    
    def process_privmsg(self, from_username, source, target, msg):
        self._bot._identify_user(source, self._on_privmsg_user_identified, source, target, msg)
    
    def _on_privmsg_user_identified(self, username, source, target, msg):
        while "  " in msg:
            msg = msg.replace("  ", " ")
        msg = msg.strip()
        words = msg.split()
        words[0] = words[0].lower()
        if username and words[0] == "banlist" and username in self._operators.setdefault(words[1], []):
            self._start_task(self._banlist, source, words[1])
