#! /usr/bin/python
# -*- coding=utf-8 -*-

from Cinnabot.BasePlugin import BasePlugin
import datetime
import tempfile
import urllib
from lxml.html import html5parser

USE_DB = True
DB_UPGRADES = {
    1: [
        """CREATE TABLE IF NOT EXISTS `params` (
            `key` TEXT PRIMARY KEY,
            `value` TEXT
        )"""
    ],
    2: [
        """CREATE TABLE IF NOT EXISTS `index` (
            `url` TEXT,
            `word` TEXT,
            `score` INTEGER
        )"""
    ]
}

NODES_WEIGHTS = {
    "{http://www.w3.org/1999/xhtml}title": 5,
    "{http://www.w3.org/1999/xhtml}h1": 3,
}

class HTMLNode(object):
    def __init__(self, xml_node):
        self._xml_node = xml_node
    
    def find(self, elname = None, maxdepth = -1, **params):
        res = []
        if elname == None or (type(self._xml_node.tag) == str and self._xml_node.tag.split("}")[-1] == elname):
            add = True
            for i in params:
                if self._xml_node.attrib.get(i, None) != params[i]:
                    add = False
                    break
            if add:
                res.append(self)
        if maxdepth != 0:
            for child in self._xml_node:
                res += HTMLNode(child).find(elname, maxdepth - 1, **params)
        return res
    
    def getContent(self):
        if self._xml_node.text:
            res = self._xml_node.text
        else:
            res = ""
        for child in self._xml_node:
            res += HTMLNode(child).getContent()
        if self._xml_node.tail:
            res += self._xml_node.tail
        return res
    
    def prop(self, prop_name):
        return self._xml_node.attrib.get(prop_name, None)
    
    def _get_children(self):
        res = []
        for child in self._xml_node:
            res.append(HTMLNode(child))
        return res
    children = property(_get_children)
    
    def _get_name(self):
        return self._xml_node.tag
    name = property(_get_name)

class Indexer(object):
    def __init__(self, url):
        self._base_url = url
        self._processed_urls = []
        self._scores = {}
        self._urls_to_process = []
    
    def _process_node(self, url, node):
        if node.children:
            for i in node.children:
                self._process_node(url, i)
        else:
            data = node.getContent()
            for i in ".,:;!?\n":
                data = data.replace(i, " ")
            while "  " in data:
                data = data.replace("  ", " ")
            for word in data.lower().split(" "):
                if word:
                    self._scores.setdefault(url, {})[word] = self._scores.setdefault(url, {}).setdefault(word, 0) + NODES_WEIGHTS.setdefault(node.name, 1)
        if node.name == "{http://www.w3.org/1999/xhtml}a":
            new_url = urllib.basejoin(url, node.prop("href")).split("?")[0].split("#")[0]
            if new_url.startswith(self._base_url) and not new_url in self._processed_urls and not new_url in self._urls_to_process:
                self._urls_to_process.append(new_url)
    
    def _process_url(self, url):
        self._processed_urls.append(url)
        tree = html5parser.parse(url)
        node = HTMLNode(tree.getroot())
        self._process_node(url, node)
        if self._urls_to_process:
            self._process_url(self._urls_to_process.pop())
        
    def run(self):
        self._process_url(self._base_url)
        return self._scores

class MintDocPlugin(BasePlugin):
    def __init__(self, bot, plugin_name):
        BasePlugin.__init__(self, bot, plugin_name)
        
        bot._irc.execute_every(3600, self._check_need_index)
    
    def _index(self):
        self._db_query("REPLACE INTO `params` (`key`, `value`) VALUES ('last_index_date', ?)", [datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")])
        
        data = Indexer(self._get_config("base_url")).run()
        self._db_query("DELETE FROM `index` WHERE 1")
        query_params = []
        for url in data:
            for word in data[url]:
                query_params += [url, word, data[url][word]]
        while query_params:
            cur_query_params, query_params = query_params[:3], query_params[3:]
            self._db_query("INSERT INTO `index` (`url`, `word`, `score`) VALUES " + ", ".join(["(?, ?, ?)"] * (len(cur_query_params) / 3)), cur_query_params)
        
        res = []
        if self._has_config("index_info_usernames"):
            for i in self._get_config("index_info_usernames").split(","):
                res.append(self.privmsg_response(i, "Docs index complete"))
        return res
    
    def _check_need_index(self):
        last_update = self._db_query("SELECT `value` FROM `params` WHERE `key` = 'last_index_date'")
        if len(last_update) != 1 or last_update[0][0] < (datetime.datetime.utcnow() - datetime.timedelta(1)).strftime("%Y-%m-%d %H:%M:%S"):
            self._start_task(self._index)
    
    def process_channel_message(self, source, target, msg):
        words = [m.lower() for m in msg.split(" ") if m != ""]
        if words[0] == "!docs" and len(words) > 1:
            if "|" in words:
                i = words.index("|")
                dest = " ".join(words[i+1:])
                words = words[1:i]
            else:
                dest = None
                words = words[1:]
            if len(words) > 0:
                res = self._db_query("SELECT `url` FROM `index` WHERE `word` IN (" + ", ".join(["?"] * len(words)) + ") GROUP BY `url` ORDER BY SUM(`score`) DESC LIMIT 1", words)
                if res:
                    if dest:
                        return self.privmsg_response(target, dest + ", " + res[0][0])
                    else:
                        return self.privmsg_response(target, res[0][0])
    
    def process_privmsg(self, from_username, source, target, msg):
        if from_username in self._get_config("admin_usernames").split(",") and msg == "docsindex":
            self._start_task(self._index)
