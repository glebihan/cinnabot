#! /usr/bin/python
# -*- coding=utf-8 -*-

from Cinnabot.BasePlugin import BasePlugin
import urllib
import urlparse
import json
import httplib2
import BaseHTTPServer

class GitHubWebHookPluginServerRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def do_POST(self):
        postdata = json.loads(self.headers.fp.read(eval(self.headers['content-length'])))
        
        if "commits" in postdata:
            self.server.plugin._start_task(self.server.plugin.handle_commits, postdata)

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
            resp, content = c.request("https://www.googleapis.com/urlshortener/v1/url?key=" + self._get_config("google_url_shortener_api_key"), "POST", headers = {"Content-Type": "application/json"}, body = json.dumps({"longUrl": url}))
            res = json.loads(content)["id"]
        except:
            res = url
        return res
    
    def _run_server(self):
        server = GitHubWebHookPluginServer(self, int(self._get_config('server_port')))
        server.serve_forever()
    
    def handle_commits(self, postdata):
        res = []
        sentence = "\x0f[\x0313%(repository)s\x0f] \x0315%(pusher)s\x0f pushed \x02%(nb_commits)d\x0f new commit" + ("", "s")[len(postdata['commits']) > 1] + " to \x0306%(branch)s\x0f: \x0302\x1f%(url)s\x0f"
        res.append(self.privmsg_response(self._get_config('output_channel'), sentence % {
            'branch': postdata['ref'].split('/')[-1],
            'repository': postdata['repository']['name'],
            'pusher': postdata['pusher']['name'],
            'nb_commits': len(postdata['commits']),
            'url': self._shorten_url(postdata['head_commit']['url'])
        }))
        commit_sentence = "\x0f\x0313%(repository)s\x0f/\x0306%(branch)s\x0f \x0314%(id)s\x0f \x0315%(author)s\x0f: %(message)s"
        for commit in postdata['commits']:
            res.append(self.privmsg_response(self._get_config('output_channel'), commit_sentence % {
                'branch': postdata['ref'].split('/')[-1],
                'repository': postdata['repository']['name'],
                'author': commit['author']['name'],
                'id': commit['id'][:7],
                'message': commit['message']
            }))
        return res
