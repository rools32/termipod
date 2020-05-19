# -*- coding: utf-8 -*-
#
# termipod
# Copyright (c) 2020 Cyril Bordage
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
import multiprocessing
import subprocess
import time
import re

import os.path

import termipod.rss as rss
import termipod.yt as yt
from termipod.utils import ts_to_date, str_to_filename


class DownloadError(Exception):
    pass


def get_all_data(url, opts, print_infos):
    if 'youtube' in url:
        data = yt.get_all_data(url, opts, print_infos)

    else:
        data = rss.get_all_data(url, opts, print_infos)
        data['addcount'] = -1

    if 'mask' in opts and len(opts['mask']):
        apply_mask(data, re.compile(opts['mask']))

    return data


def get_new_data(channel, opts, print_infos):
    if 'mask' not in opts:
        opts['mask'] = channel['mask']

    if channel['type'] == 'youtube':
        data = yt.get_new_data(channel, opts, print_infos)

    else:  # rss
        data = rss.get_new_data(channel, opts, print_infos)
        data['addcount'] = -1

    if len(channel['mask']):
        apply_mask(data, channel['mask'])

    return data


def apply_mask(data, mask):
    regex = re.compile(mask)
    data['items'] = [medium for medium in data['items']
                     if regex.match(medium['title'])]
    return data


def update_medium(medium, print_infos):
    channel_type = medium['channel']['type']
    if channel_type == 'youtube':
        updated = yt.update_medium(medium, print_infos)
    else:
        print('Not implemented on this type of channel')
        updated = False

    return updated


def get_clean_url(url):
    if not url.startswith('http'):  # local file
        return url
    elif 'youtube' in url:
        return yt.get_clean_url(url)
    else:  # rss
        return url


def expand_link(channel, link):
    if channel['type'] == 'youtube':
        return yt.expand_link(link)
    else:
        return link


def shrink_link(channel, link):
    if channel['type'] == 'youtube':
        return yt.shrink_link(link)
    else:
        return link


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
    def __init__(self, item_list, print_infos, wait=False):
        self.nthreads = 2
        self.item_list = item_list
        self.print_infos = print_infos
        self.queue = Queue()
        self.wait = wait
        self.max_retries = 3
        self.cancel_requests = {}

        # Set up some threads to fetch the items to download
        for i in range(self.nthreads):
            worker = Thread(target=self.handle_queue)
            worker.daemon = True
            worker.start()

        for medium in self.item_list.media:
            if 'download' == medium['location']:
                self.add(medium, update=False)
        if self.wait:
            self.wait_done()

    def handle_queue(self):
        """This is the worker thread function. It processes items in the queue one
        after another.  These daemon threads go into an infinite loop, and only
        exit when the main thread ends."""
        q = self.queue

        # Wait for UI to be ready
        if not self.wait:
            time.sleep(2)

        while True:
            medium = q.get()
            try:
                self.download(medium)
                q.task_done()
            except DownloadError:
                if not medium['link'] in self.handle_queue.retries:
                    self.handle_queue.retries[medium['link']] = 1

                if self.max_retries <= \
                        self.handle_queue.retries[medium['link']]:
                    continue

                self.handle_queue.retries[medium['link']] += 1
                sleep(5)
                self.add(medium, update=False)
    handle_queue.retries = {}

    def add(self, medium, update=True):
        if update:
            self.print_infos('Add to download: %s' % medium['title'])
            medium['location'] = 'download'
            self.item_list.db.update_medium(medium)
            self.item_list.update_medium_areas(modified_media=[medium])

        if medium['link'] in self.cancel_requests:
            del self.cancel_requests[medium['link']]

        self.queue.put(medium)

    def wait_done(self):
        self.queue.join()

    def download(self, medium):
        link = medium['link']
        channel = medium['channel']

        if link in self.cancel_requests:  # If download was cancelled
            return

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
            dl_func = rss.download

        elif 'youtube' == channel['type']:
            filename = "%s/%s_%s.%s" % (path, ts_to_date(medium['date']),
                                        str_to_filename(medium['title']),
                                        'mp4')
            dl_func = yt.download

        ret = multiprocessing.Queue()
        # Download needs to be done as a new process to be able to cancel it
        p = multiprocessing.Process(
            target=self.download_task,
            args=(ret, (dl_func, link, filename, self.print_infos)))
        p.daemon = True
        p.start()

        # While download is running, check if needs to be cancelled
        while p.is_alive():
            time.sleep(1)
            if link in self.cancel_requests:
                p.kill()
                del self.cancel_requests[link]
        p.join()

        if not p.exitcode:
            if ret.get_nowait():  # Download failed
                self.print_infos('Download failed %s' % link)
                raise(DownloadError)
            else:
                self.print_infos('Downloaded (%s)' % medium['title'])
                # Change location and filename
                medium['filename'] = filename
                medium['location'] = 'local'

                if 0 == medium['duration']:
                    medium['duration'] = get_duration(medium)

        else:
            self.print_infos('Download cancelled %s' % link)

        self.item_list.db.update_medium(medium)
        self.item_list.update_medium_areas(modified_media=[medium])

        return 0

    def download_task(self, ret, args):
        ret.put(args[0](*args[1:]))

    def cancel_download(self, medium):
        self.cancel_requests[medium['link']] = True
        medium['location'] = 'remote'
        self.item_list.db.update_medium(medium)
        self.item_list.update_medium_areas(modified_media=[medium])
