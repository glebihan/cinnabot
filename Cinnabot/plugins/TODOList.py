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
    "^\\ *add(\\ +(low|medium|high))?\\ +todo\\ (.*)$": "add_todo",
    "^\\ *set\\ +todo\\ +priority\\ +([0-9]+)\\ +(low|medium|high)\\ *$": "set_todo_priority",
    "^\\ *delete\\ +todo\\ +([0-9]+)\\ *$": "delete_todo",
    "^\\ *remove\\ +todo\\ +([0-9]+)\\ *$": "delete_todo",
    "^\\ *clear\\ +todo\\ +list\\ *$": "clear_todo_list",
    "^\\ *todo\\ +help\\ *$": "help",
}

PRIORITY_COLORS = {
    "high": u"\x02",
    "medium": "",
    "low": u"\x0314"
}

TODO_HELP_TEXT = """To manage your TODO list, you can use the following commands :
/msg %nickname% todo                                                        # shows your TODO list
/msg %nickname% show todo                                                   # shows your TODO list
/msg %nickname% show todo list                                              # shows your TODO list
/msg %nickname% todo list                                                   # shows your TODO list
/msg %nickname% add [low|medium|high] todo <todo_item>                      # adds an item to your TODO list with an optional priority (defaults to medium)
/msg %nickname% remove todo <todo_item_index>                               # removes the item in position #todo_item_index from your list (index starts at 1)
/msg %nickname% delete todo <todo_item_index>                               # removes the item in position #todo_item_index from your list (index starts at 1)
/msg %nickname% clear todo list                                             # clears your TODO list
/msg %nickname% set todo priority <todo_item_index> low|medium|high         # updates the priority of an item in your TODO list"""

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
                
                # temporary patch to convert existing config
                for username in self._todos:
                    for i in range(len(self._todos[username])):
                        if type(self._todos[username][i]) != dict:
                            self._todos[username][i] = {"label": self._todos[username][i], "priority": "medium"}
            except:
                pass
    
    def _save_todos(self):
        filename = os.path.join(os.getenv("HOME"), ".config", "cinnabot", "TODOList.list")
        f = open(filename, "w")
        f.write(json.dumps(self._todos))
        f.close()
            
    def process_highlight(self, from_username, source, target, msg):
        for regexp in self._commands:
            match_data = regexp.match(msg)
            if match_data:
                if from_username:
                    return self._commands[regexp](*((from_username, source, target) + match_data.groups()))
                else:
                    return self.notice_response(source.split("!")[0], "You must be logged in to use the TODO list")
    
    def process_privmsg(self, from_username, source, target, msg):
        return self.process_highlight(from_username, source, target, msg)
    
    def show_todo_list(self, from_username, source, target):
        logging.info("TODOListPlugin:show_todo_list:" + from_username + ":" + source + ":" + target)
        
        res = []
        todos = self._todos.get(from_username, [])
        if len(todos) > 0:
            for i in range(len(todos)):
                res.append(self.notice_response(source.split("!")[0], PRIORITY_COLORS[todos[i]["priority"]] + "TODO #%d (%s) : %s" % (i + 1, todos[i]["priority"], todos[i]["label"])))
        else:
            res = self.notice_response(source.split("!")[0], "Nothing in the TODO list")
        
        return res
    
    def add_todo(self, from_username, source, target, ig, priority, todo_item):
        logging.info("TODOListPlugin:add_todo:" + from_username + ":" + source + ":" + target + ":" + todo_item)
        
        if not priority:
            priority = "medium"
        
        self._todos.setdefault(from_username, []).append({"label": todo_item, "priority": priority})
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
    
    def set_todo_priority(self, from_username, source, target, todo_index, priority):
        logging.info("TODOListPlugin:set_todo_priority:" + from_username + ":" + source + ":" + target + ":" + todo_index + ":" + priority)
        
        todo_index = int(todo_index) - 1
        todos = self._todos.get(from_username, [])
        if todo_index < len(todos):
            todos[todo_index]["priority"] = priority
            self._save_todos()
            return self.notice_response(source.split("!")[0], "Priority updated")
        else:
            return self.notice_response(source.split("!")[0], "TODO item not found")
    
    def clear_todo_list(self, from_username, source, target):
        logging.info("TODOListPlugin:clear_todo_list:" + from_username + ":" + source + ":" + target)
        
        if from_username in self._todos:
            del self._todos[from_username]
            self._save_todos()
        
        return self.notice_response(source.split("!")[0], "TODO list cleared")
    
    def help(self, from_username, source, target):
        res = []
        for line in TODO_HELP_TEXT.replace("%nickname%", self._bot._irc_server_connection.get_nickname()).splitlines():
            res.append(self.notice_response(source.split("!")[0], line))
        return res
