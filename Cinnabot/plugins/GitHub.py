#! /usr/bin/python
# -*- coding=utf-8 -*-

from Cinnabot.BasePlugin import BasePlugin
import urllib
import json

class GitHubPlugin(BasePlugin):
    def _load_packages_list(self):
        self._packages_list = []
        page = 1
        repos = self._retrieve_github_info("https://api.github.com/users/linuxmint/repos?access_token=%s" % self._get_config("github_access_token"))
        while repos and len(repos) > 0:
            for repo in repos:
                self._packages_list.append(repo["name"])
            page += 1
            repos = self._retrieve_github_info("https://api.github.com/users/linuxmint/repos?access_token=%s&page=%d" % (self._get_config("github_access_token"), page))
    
    def _retrieve_github_info(self, url):
        try:
            filename, message = urllib.urlretrieve(url)
            f = open(filename)
            data = f.read()
            f.close()
            return json.loads(data)
        except:
            return None
    
    def _format_issue_info(self, issue_info):
        try:
            #~ for i in issue_info:
                #~ print i, issue_info[i]
            return u"[\x0313%s\x0f] \x0314%s #%d, %s\x0f \x0315%s\x0f: %s \x0302\x1f%s\x0f" % (issue_info["html_url"].split("/")[-3], ("Issue", "Pull request")[("pull_request" in issue_info) and ("url" in issue_info["pull_request"]) and (issue_info["pull_request"]["url"] != None)], issue_info["number"], issue_info["state"], issue_info["user"]["login"], issue_info["title"], issue_info["html_url"])
        except:
            return None
            
    def _format_commit_info(self, commit_info):
        try:
            #~ for i in commit_info:
                #~ print i, commit_info[i]
            return "[\x0313%s\x0f] \x0314Commit %s\x0f \x0315%s\x0f: %s" % (commit_info["html_url"].split("/")[-3], commit_info["sha"], commit_info["author"]["name"], commit_info["message"])
        except:
            return None
            
    def process_channel_message(self, source, target, msg):
        if not hasattr(self, "_packages_list"):
            self._load_packages_list()
        while u'\x03' in msg:
            i = msg.index(u'\x03')
            msg = msg[:i] + msg[i+3:]
        msg = msg.replace("\x0f", "")
        words = [word.rstrip().lstrip() for word in msg.split(" ") if word.rstrip().lstrip() != ""]
        words_lower = [word.lower() for word in words]
        other_words = []
        for word in words_lower:
            new_word = word
            for c in ",:;./[]()":
                new_word = new_word.replace(c, " ")
                if " " in new_word:
                    other_words += new_word.split(" ")
        issues_url_words = [word for word in words if word.startswith("https://github.com/") and ("/issues/" in word or "/pull/" in word)]
        issues_urls = []
        for url in issues_url_words:
            issues_urls.append(url.replace("https://github.com/", "https://api.github.com/repos/").replace("/pull/", "/issues/") + "?access_token=" + self._get_config("github_access_token"))
        packages_list = []
        for package in self._packages_list:
            if package.lower() in words_lower or package.lower() in other_words:
                packages_list.append(package)
        issues_numbers = []
        for i in range(len(words)):
            if words[i].lower() == "issue" and i < len(words) - 1:
                next_word = words[i + 1];
                try:
                    if next_word[-1] in ",.;:":
                        next_word = next_word[:-1]
                    issue_number = int(next_word)
                    issues_numbers.append(issue_number)
                except:
                    pass
            elif words[i][0] == "#":
                try:
                    if words[i][-1] in ",.;:":
                        words[i] = words[i][:-1]
                    issue_number = int(words[i][1:])
                    issues_numbers.append(issue_number)
                except:
                    pass
        if len(packages_list) == 0:
            packages_list = self._packages_list
        if len(issues_numbers) > 0:
            for package in packages_list:
                for issue_number in issues_numbers:
                    issues_urls.append("https://api.github.com/repos/linuxmint/%s/issues/%d?access_token=%s" % (package, issue_number, self._get_config("github_access_token")))
        for url in issues_urls:
            issue_info = self._retrieve_github_info(url)
            if issue_info:
                output_message = self._format_issue_info(issue_info)
                if output_message:
                    return self.privmsg_response(target, output_message)
        commits_url_words = [word for word in words if word.startswith("https://github.com/") and "/commit/" in word]
        commits_urls = []
        for url in commits_url_words:
            commits_urls.append(url.replace("https://github.com/", "https://api.github.com/repos/").replace("/commit/", "/git/commits/") + "?access_token=" + self._get_config("github_access_token"))
        for url in commits_urls:
            commit_info = self._retrieve_github_info(url)
            if commit_info:
                output_message = self._format_commit_info(commit_info)
                if output_message:
                    return self.privmsg_response(target, output_message.replace("\n", " "))
