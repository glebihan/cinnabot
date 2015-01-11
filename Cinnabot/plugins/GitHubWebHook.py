#! /usr/bin/python
# -*- coding=utf-8 -*-

from Cinnabot.BasePlugin import BasePlugin
import urllib
import urlparse
import json
import httplib2
import BaseHTTPServer
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
        
        self._start_task(self._run_server)
    
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
        if len(title) > 70:
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
        sentence = "\x0f[\x0313%(repository)s\x0f] \x0315%(pusher)s\x0f pushed \x02%(nb_commits)d\x0f new commit" + ("", "s")[len(postdata['commits']) > 1] + " to \x0306%(branch)s\x0f: \x0302\x1f%(url)s\x0f"
        data = {
            'branch': postdata['ref'].split('/')[-1],
            'repository': postdata['repository']['name'],
            'pusher': postdata['pusher']['name'],
            'nb_commits': len(postdata['commits']),
            'url': self._shorten_url(postdata['compare'])
        }
        self._log(sentence % data)
        res.append(self.privmsg_response(self._get_config('output_channel'), sentence % data))
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
