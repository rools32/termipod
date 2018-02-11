# -*- coding: utf-8 -*-
#
# termipod
# Copyright (c) 2018 Cyril Bordage
#
# termipod is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# termipod is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
import re
from datetime import datetime
from time import mktime, time

import feedparser as fp
import youtube_dl as ytdl

from termipod.utils import print_log, printable_str


class DownloadLogger(object):
    def __init__(self, print_infos, url):
        self.print_infos = print_infos
        self.url = url
        self.step = 0

    def debug(self, msg):
        regex = '.*\[download\] *([0-9.]*)% of *[0-9.]*.i_b ' \
                'at *[0-9.]*.i_b/s ETA ([0-9:]*)'
        match = re.match(regex, msg)
        if match is not None:
            percentage = int(float(match.groups()[0]))
            eta = match.groups()[1]
            if percentage >= self.step:
                self.print_infos('Downloading %s (%d%% ETA %s)...' %
                                 (self.url, percentage, eta))
                self.step = int(percentage/10+1)*10

    def warning(self, msg):
        self.print_infos('[YTDL warning] %s' % msg)

    def error(self, msg):
        self.print_infos('[YTDL error] %s' % msg)


class DataLogger(object):
    def __init__(self, print_infos, url):
        self.print_infos = print_infos
        self.url = url

    def debug(self, msg):
        regex = "\[download\] Downloading video (\d*) of (\d*)"
        match = re.match(regex, msg)
        if match is not None:
            current = float(match.groups()[0])
            total = float(match.groups()[1])
            self.print_infos('Adding %s (%d%%)' %
                             (self.url, int(current*100/total)))

    def warning(self, msg):
        self.print_infos('[YTDL warning] %s' % msg)

    def error(self, msg):
        self.print_infos('[YTDL error] %s' % msg)


def download(url, filename, print_infos=print):
    ydl_opts = {'logger': DownloadLogger(print_infos, url),
                'outtmpl': filename, 'format': 'mp4'}
    with ytdl.YoutubeDL(ydl_opts) as ydl:
        try:
            return ydl.download([url])
        except ytdl.DownloadError:
            return 1


def get_data(url, print_infos=print, new=False):
    # If first add, we use ytdl to get old media
    if new:
        ydl_opts = {'logger': DataLogger(print_infos, url),
                    'ignoreerrors': True}
        with ytdl.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(url, download=False)
        if result is None or result['entries'] is None:
            print_infos("Cannot get data from %s" % url)
            return None

        entries = result['entries']

        # Find channel name
        channel_title = None
        for entry in entries:
            if entry is not None:
                channel_title = printable_str(entry['uploader'])
                break

        if channel_title is None:
            return None

        data = {}
        data['url'] = url
        data['title'] = channel_title
        data['updated'] = int(time())
        data['type'] = 'youtube'

        data['items'] = []
        for entry in entries:
            if entry is None:
                continue
            medium = {}
            medium['channel'] = data['title']
            medium['url'] = url
            medium['title'] = printable_str(entry['title'])
            medium['date'] = int(mktime(datetime.strptime(
                entry['upload_date'], "%Y%m%d").timetuple()))
            medium['description'] = entry['description']
            medium['link'] = entry['webpage_url']
            medium['duration'] = entry['duration']
            data['items'].append(medium)

        return data

    else:
        feed_url = url.replace('channel/', 'feeds/videos.xml?channel_id=')
        rss = fp.parse(feed_url)

        feed = rss.feed
        if not feed:
            print_infos('Cannot load '+feed_url)
            return None

        data = {}
        data['url'] = url
        data['title'] = printable_str(feed['title'])
        data['type'] = 'youtube'

        updated = 0
        data['items'] = []
        entries = rss.entries
        for entry in entries:
            medium = {}
            medium['channel'] = data['title']
            medium['url'] = url
            medium['title'] = printable_str(entry['title'])
            medium['date'] = int(mktime(entry['published_parsed']))
            medium['description'] = entry['description']
            medium['link'] = entry['link']
            updated = max(updated, medium['date'])
            data['items'].append(medium)

        # Published parsed is the date of creation of the channel, so we take
        # the one from entries
        data['updated'] = updated

        return data
