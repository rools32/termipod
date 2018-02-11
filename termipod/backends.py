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

import os
import shlex
from time import sleep
from queue import Queue
from threading import Thread
import subprocess

import os.path

import termipod.rss as rss
import termipod.yt as yt
from termipod.utils import *


def get_data(url, print_infos=print, new=False):
    if not url.startswith('http'):  # local file
        data = rss.get_data(url, print_infos)
    elif 'youtube' in url:
        data = yt.get_data(url, print_infos, new)
    else:
        data = rss.get_data(url, print_infos)
    return data


def get_duration(medium):
    filename = os.path.abspath(medium['filename']).replace('"', '\\"')
    commandline = 'ffprobe -i "%s" -show_entries ' \
                  'format=duration -v quiet -of csv="p=0"' % filename
    args = shlex.split(commandline)
    result = subprocess.Popen(
            args,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    output = result.communicate()
    duration = int(float(output[0]))
    return duration


class DownloadManager():
    def __init__(self, item_list, wait=False, print_infos=print):
        self.nthreads = 2
        self.item_list = item_list
        self.print_infos = print_infos
        self.queue = Queue()
        self.wait = wait
        self.max_retries = 3

        # Set up some threads to fetch the items to download
        for i in range(self.nthreads):
            worker = Thread(target=self.handle_queue)
            worker.daemon = True
            worker.start()

        for medium in self.item_list.media:
            if 'download' == medium['location']:
                channel = self.item_list.db.get_channel(medium['url'])
                self.add(medium, channel, update=False)
        if self.wait:
            self.wait_done()

    def handle_queue(self):
        """This is the worker thread function. It processes items in the queue one
        after another.  These daemon threads go into an infinite loop, and only
        exit when the main thread ends."""
        q = self.queue
        while True:
            medium, channel = q.get()
            ret = self.download(medium, channel)
            q.task_done()
            if ret is None:
                if not medium['link'] in self.handle_queue.retries:
                    self.handle_queue.retries[medium['link']] = 1

                if self.max_retries <= \
                        self.handle_queue.retries[medium['link']]:
                    continue

                self.handle_queue.retries[medium['link']] += 1
                sleep(5)
                self.add(medium, channel, update=False)
    handle_queue.retries = {}

    def add(self, medium, channel, update=True):
        if update:
            self.print_infos('Add to download: %s' % medium['title'])
            medium['location'] = 'download'
            self.item_list.db.update_medium(medium)
            self.item_list.update_medium_areas(modified_media=[medium])
        self.queue.put((medium, channel))

    def wait_done(self):
        self.queue.join()

    def download(self, medium, channel):
        link = medium['link']

        # Set filename # TODO handle collision
        path = str_to_filename(channel['title'])
        if not os.path.exists(path):
            os.makedirs(path)

        # Download file
        self.print_infos('Download %s...' % medium['title'])
        if 'rss' == channel['type']:
            ext = link.split('.')[-1]
            filename = "%s/%s_%s.%s" % (
                    path, ts_to_date(medium['date']),
                    str_to_filename(medium['title']), ext)
            ret = rss.download(link, filename, self.print_infos)

        elif 'youtube' == channel['type']:
            filename = "%s/%s_%s.%s" % (path, ts_to_date(medium['date']),
                                        str_to_filename(medium['title']),
                                        'mp4')
            ret = yt.download(link, filename, self.print_infos)

        if 0 != ret:  # Download did not happen
            self.print_infos('Download failed %s' % link)
            return

        self.print_infos('Downloaded (%s)' % medium['title'])

        # Change location and filename
        medium['filename'] = filename
        medium['location'] = 'local'

        if 0 == medium['duration']:
            medium['duration'] = get_duration(medium)

        self.item_list.db.update_medium(medium)
        self.item_list.update_medium_areas(modified_media=[medium])

        return 0
