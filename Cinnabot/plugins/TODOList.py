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
    "^\\ *add\\ +todo\\ (.*)$": "add_todo",
    "^\\ *delete\\ +todo\\ +([0-9]+)\\ *$": "delete_todo",
    "^\\ *remove\\ +todo\\ +([0-9]+)\\ *$": "delete_todo"
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
            
    def process_highlight(self, source, target, msg):
        for regexp in self._commands:
            match_data = regexp.match(msg)
            if match_data:
                return self._commands[regexp](*((source, target) + match_data.groups()))
    
    def process_privmsg(self, source, target, msg):
        return self.process_highlight(source, target, msg)
    
    def show_todo_list(self, source, target):
        logging.info("TODOListPlugin:show_todo_list:" + source + ":" + target)
        
        res = []
        todos = self._todos.get(source, [])
        for i in range(len(todos)):
            res.append(self.notice_response(source.split("!")[0], "TODO #%d : %s" % (i + 1, todos[i])))
        
        return res
    
    def add_todo(self, source, target, todo_item):
        logging.info("TODOListPlugin:add_todo:" + source + ":" + target + ":" + todo_item)
        
        self._todos.setdefault(source, []).append(todo_item)
        self._save_todos()
        if target.startswith("#"):
            resp_target = target
        else:
            resp_target = source.split("!")[0]
        return self.privmsg_response(resp_target, "Item added to TODO list")
    
    def delete_todo(self, source, target, todo_index):
        logging.info("TODOListPlugin:delete_todo:" + source + ":" + target + ":" + todo_index)
        
        if target.startswith("#"):
            resp_target = target
        else:
            resp_target = source.split("!")[0]
        
        todo_index = int(todo_index) - 1
        todos = self._todos.get(source, [])
        if todo_index < len(todos):
            del todos[todo_index]
            self._save_todos()
            return self.privmsg_response(resp_target, "TODO item deleted")
        else:
            return self.privmsg_response(resp_target, "TODO item not found")
