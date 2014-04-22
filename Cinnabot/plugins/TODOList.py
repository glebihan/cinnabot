#! /usr/bin/python
# -*- coding=utf-8 -*-

from Cinnabot.BasePlugin import BasePlugin
import re
import logging
import os
import json

TODO_LIST_COMMANDS = {
    "^\\ *show\\ +todo\\ +list\\ *$": "show_todo_list",
    "^\\ *show\\ +todo\\ *$": "show_todo_list",
    "^\\ *todo\\ +list\\ *$": "show_todo_list",
    "^\\ *todo\\ *$": "show_todo_list",
    "^\\ *add\\ +todo\\ (.*)$": "add_todo",
    "^\\ *delete\\ +todo\\ +([0-9]+)\\ *$": "delete_todo",
    "^\\ *remove\\ +todo\\ +([0-9]+)\\ *$": "delete_todo",
    "^\\ *clear\\ +todo\\ +list\\ *$": "clear_todo_list",
}

class TODOListPlugin(BasePlugin):
    def __init__(self, bot, plugin_name):
        BasePlugin.__init__(self, bot, plugin_name)
        
        self._commands = {}
        for regexp in TODO_LIST_COMMANDS:
            self._commands[re.compile(regexp, re.IGNORECASE)] = getattr(self, TODO_LIST_COMMANDS[regexp])
        
        self._load_todos()
    
    def _load_todos(self):
        self._todos = {}
        filename = os.path.join(os.getenv("HOME"), ".config", "cinnabot", "TODOList.list")
        if os.path.exists(filename):
            try:
                f = open(filename, "r")
                self._todos = json.loads(f.read())
                f.close()
            except:
                pass
    
    def _save_todos(self):
        filename = os.path.join(os.getenv("HOME"), ".config", "cinnabot", "TODOList.list")
        f = open(filename, "w")
        f.write(json.dumps(self._todos))
        f.close()
            
    def process_highlight(self, from_username, source, target, msg):
        if not from_username:
            return self.notice_response(source.split("!")[0], "You must be logged in to use the TODO list")
            
        for regexp in self._commands:
            match_data = regexp.match(msg)
            if match_data:
                return self._commands[regexp](*((from_username, source, target) + match_data.groups()))
    
    def process_privmsg(self, from_username, source, target, msg):
        return self.process_highlight(from_username, source, target, msg)
    
    def show_todo_list(self, from_username, source, target):
        logging.info("TODOListPlugin:show_todo_list:" + from_username + ":" + source + ":" + target)
        
        res = []
        todos = self._todos.get(from_username, [])
        if len(todos) > 0:
            for i in range(len(todos)):
                res.append(self.notice_response(source.split("!")[0], "TODO #%d : %s" % (i + 1, todos[i])))
        else:
            res = self.notice_response(source.split("!")[0], "Nothing in the TODO list")
        
        return res
    
    def add_todo(self, from_username, source, target, todo_item):
        logging.info("TODOListPlugin:add_todo:" + from_username + ":" + source + ":" + target + ":" + todo_item)
        
        self._todos.setdefault(from_username, []).append(todo_item)
        self._save_todos()
        return self.notice_response(source.split("!")[0], "Item added to TODO list")
    
    def delete_todo(self, from_username, source, target, todo_index):
        logging.info("TODOListPlugin:delete_todo:" + from_username + ":" + source + ":" + target + ":" + todo_index)
        
        todo_index = int(todo_index) - 1
        todos = self._todos.get(from_username, [])
        if todo_index < len(todos):
            del todos[todo_index]
            self._save_todos()
            return self.notice_response(source.split("!")[0], "TODO item deleted")
        else:
            return self.notice_response(source.split("!")[0], "TODO item not found")
    
    def clear_todo_list(self, from_username, source, target):
        logging.info("TODOListPlugin:clear_todo_list:" + from_username + ":" + source + ":" + target)
        
        if from_username in self._todos:
            del self._todos[from_username]
            self._save_todos()
        
        return self.notice_response(source.split("!")[0], "TODO list cleared")
