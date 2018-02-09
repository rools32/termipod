termipod - Podcasts and Youtube in your terminal
================================================

termipod is a curses application written in Python3 to manage your podcasts and your youtube
channels in your terminal. With it, you can:

* Mark media as read/unread/skipped
* Download media
* Automatically download new media matching a pattern
* Play media with *mpv*

Youtube channels are handled by *youtube_dl* for the first import to get all videos, but then,
for efficiency purpose, by *feedparser* reading the RSS feed provided by Google.

Requirements:

* appdirs
* feedparser
* mpv
* youtube_dl

You can install it with pip:

    pip install termipod

To run it:

    >>> # To open UI
    >>> termipod
    >>> # To show help
    >>> termipod --help
    >>> # To add an new channel and automatically new videos
    >>> termipod --add http://radiofrance-podcast.net/podcast09/rss_14257.xml --auto ".*"

termipod is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 3 of the License, or
(at your option) any later version.

termipod is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see
[http://www.gnu.org/licenses/](http://www.gnu.org/licenses/).
