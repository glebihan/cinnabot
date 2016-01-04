#! /usr/bin/python
# -*- coding=utf-8 -*-

from Cinnabot.BasePlugin import BasePlugin
import urllib
import urlparse
import json
import re
import httplib2
import BaseHTTPServer
import os
import _codecs

class GitHubWebHookPluginServerRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def do_POST(self):
        postdata = json.loads(self.headers.fp.read(eval(self.headers['content-length'])))
        
        if "commits" in postdata:
            self.server.plugin._start_task(self.server.plugin.handle_commits, postdata)
        elif "pull_request" in postdata and "action" in postdata and postdata["action"] == "opened":
            self.server.plugin._start_task(self.server.plugin.handle_open_pull_request, postdata)
        else:
            self.send_response(404)
            self.end_headers()
            return
        
        self.send_response(200)
        self.end_headers()

class GitHubWebHookPluginServer(BaseHTTPServer.HTTPServer):
    def __init__(self, plugin, port):
        BaseHTTPServer.HTTPServer.__init__(self, ('', port), GitHubWebHookPluginServerRequestHandler)
        self.port = port
        self.plugin = plugin

class GitHubWebHookPlugin(BasePlugin):
    def __init__(self, bot, plugin_name):
        BasePlugin.__init__(self, bot, plugin_name)
        
        #~ self._start_task(self._run_server)
        bot._irc.execute_every(5, self._check_webhook_queue)
    
    def _check_webhook_queue(self):
        path = os.path.join(os.getenv("HOME"), ".config", "cinnabot", "github_webhook_queue")
        files = os.listdir(path)
        while len(files):
            filename = os.path.join(path, files.pop())
            try:
                f = open(filename)
                postdata = json.loads(f.read())
                f.close()
                if "commits" in postdata:
                    self._start_task(self.handle_commits, postdata)
                elif "pull_request" in postdata and "action" in postdata and postdata["action"] == "opened":
                    self._start_task(self.handle_open_pull_request, postdata)
            except:
                pass
            try:
                os.unlink(filename)
            except:
                pass
    
    def _shorten_url(self, url):
        try:
            c = httplib2.Http()
            resp, content = c.request("http://git.io", "POST", headers = {"Content-Type": "multipart/form-data"}, body = urllib.urlencode({'url': url}))
            res = resp['location']
        except:
            res = url
        return res
    
    def _run_server(self):
        server = GitHubWebHookPluginServer(self, int(self._get_config('server_port')))
        server.serve_forever()
    
    def handle_open_pull_request(self, postdata):
        self._log(str(postdata))
        res = []
        sentence = "\x0f[\x0313%(repository)s\x0f] \x0315%(sender)s\x0f opened pull request #%(number)d: %(title)s (\x0306%(base)s...%(head)s\x0f) \x0302\x1f%(url)s\x0f"
        title = postdata['pull_request']['title'].replace("\n", " ").replace("\r", " ")
        if u"\u2026" in title:
            title = title.split(u"\u2026")[0] + "..."
        elif len(title) > 70:
            title = title[:67] + "..."
        data = {
            'repository': postdata['repository']['name'],
            'sender': postdata['sender']['login'],
            'title': title,
            'url': self._shorten_url(postdata['pull_request']['html_url']),
            'base': postdata['pull_request']['base']['ref'],
            'head': postdata['pull_request']['head']['ref'],
            'number': postdata['number']
        }
        self._log(sentence % data)
        res.append(self.privmsg_response(self._get_config('output_channel'), sentence % data))
        return res
        
    def handle_commits(self, postdata):
        self._log(str(postdata))
        res = []

        summary = self.make_push_summary(postdata)
        self._log(summary)
        res.append(self.privmsg_response(self._get_config('output_channel'), summary))

        commit_sentence = "\x0f\x0313%(repository)s\x0f/\x0306%(branch)s\x0f \x0314%(id)s\x0f \x0315%(author)s\x0f: %(message)s"
        for commit in postdata['commits'][:3]:
            commit_message = commit['message'].replace("\n", " ").replace("\r", " ")
            if len(commit_message) > 70:
                commit_message = commit_message[:67] + "..."
            data = {
                'branch': postdata['ref'].split('/')[-1],
                'repository': postdata['repository']['name'],
                'author': commit['author']['name'].encode('ascii', 'ignore'),
                'id': commit['id'][:7],
                'message': commit_message
            }
            self._log(commit_sentence % data)
            res.append(self.privmsg_response(self._get_config('output_channel'), commit_sentence % data))
        return res

    def make_push_summary(self, postdata):
        message = "\x0f[%s] %s" % (self._format(postdata['repository']['name'], "repo"), self._format(postdata['pusher']['name'].encode('ascii', 'ignore'), "author"))

        distinct_commits = []
        for commit in postdata['commits']:
            if commit['distinct'] and commit['message'] != "":
                distinct_commits.append(commit)
        num = len(distinct_commits)

        ref_name = re.sub("\Arefs/(heads|tags)/", "", postdata['ref'])
        if postdata['base_ref']:
            base_ref_name = re.sub("\Arefs/(heads|tags)/", "", postdata['base_ref'])

        if postdata['created']:
            if "refs/tags/" in postdata['ref']:
                message += " tagged %s at" % self._format(ref_name, "tag")
                if postdata['base_ref']:
                    message += " " + self._format(base_ref_name, "branch")
                else:
                    message += " " + self._format(postdata['after'][:7], "hash")
            else:
                message += " created " + self._format(ref_name, "branch")

                if postdata['base_ref']:
                    message += " from " + self._format(base_ref_name, "branch")
                elif num > 0:
                    message += " at " + self._format(postdata['after'][:7], "hash")

                message += " (+%s new commit%s)" % (self._format(num, "bold"), ("", "s")[num > 1])

        elif postdata['deleted']:
            message += " \00304deleted\017 %s at %s" % (self._format(ref_name, "branch"), self._format(postdata['before'][:7], "hash"))

        elif postdata['forced']:
            message += " \00304force-pushed\017 %s from %s to %s" % (self._format(ref_name, "branch"), self._format(postdata['before'][:7], "hash"), self._format(postdata['after'][:7], "hash"))

        elif len(postdata['commits']) > 0 and num == 0:
            if postdata['base_ref']:
                message += " merged %s into %s" % (self._format(base_ref_name, "branch"), self._format(ref_name, "branch"))
            else:
                message += " fast-forwarded %s from %s to %s" % (self._format(ref_name, "branch"), self._format(postdata['before'][:7], "hash"), self._format(postdata['after'][:7], "hash"))

        else:
            message += " pushed %s new commit%s to %s" % (self._format(num, "bold"), ("", "s")[num > 1], self._format(ref_name, "branch"))
        
        if not postdata['deleted']:
            if num > 1:
                url = postdata['compare']
            else:
                url = postdata['head_commit']['url']
            return message + ": \x0302\x1f%s\x0f" % self._shorten_url(url)
        else:
            return message

    def _format(self, text, t):
        before = {
            'bold':   "\x02",
            'branch': "\x0306",
            'tag':    "\x0306",
            'repo':   "\x0313",
            'hash':   "\x0314",
            'author': "\x0315"
        }
        return "%s%s\x0f" % (before[t], text)
