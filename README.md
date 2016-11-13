cinnabot
========

Simple IRC bot used to display information about issues / pull requests / commits when they're mentioned in a channel.

It watches for links to issues, pull requests and commits as well as issues and pull requests numbers, for all Linux Mint packages :
* #246
* issue 246
* Cinnamon #246
* Muffin issue 139
* https://github.com/linuxmint/Cinnamon/issues/246

When a package name is mentioned, only results for that package will be displayed.

Only the first result will be displayed even if there are several matches (eg identical issue number on several packages).

<pre>
Usage: cinnabot [options]

Options:
  -h, --help            show this help message and exit
  -c CONFIG_FILE, --config-file=CONFIG_FILE
  -d DEBUG_LEVEL, --debug-level=DEBUG_LEVEL
</pre>

