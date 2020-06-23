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
from time import sleep, mktime
from datetime import datetime
from queue import Queue
from threading import Thread
import multiprocessing
import subprocess
import re

import os.path

import termipod.rss as rss
import termipod.yt as yt
from termipod.utils import str_to_filename, ts_to_date, noop, run_all
from termipod.backends_exceptions import DownloadError


def media_add_missing_fields(data, browse=False):
    fields = (
        ('date', 0),
        ('duration', 0),
        ('description', ''),
        ('thumbnail', ''),
    )

    for f, v in fields:
        if f not in data:
            data[f] = v

    if browse:
        data['location'] = 'browse'
        data['filename'] = ''


def channel_add_missing_fields(data, browse=False):
    fields = (
        ('addcount', -1),
        ('thumbnail', ''),
    )

    for f, v in fields:
        if f not in data:
            data[f] = v

    for item in data['items']:
        media_add_missing_fields(item, browse)


def get_all_data(url, opts, print_infos, browse=False):
    if 'youtube' in url:
        data = yt.get_all_data(url, opts, print_infos)

    else:
        data = rss.get_all_data(url, opts, print_infos)

    if 'mask' in opts and opts['mask']:
        apply_mask(data, re.compile(opts['mask']))

    channel_add_missing_fields(data, browse)
    return data


def get_new_data(channel, opts, print_infos, force_all=False):
    if 'mask' not in opts:
        opts['mask'] = channel['mask']

    if channel['type'] == 'youtube':
        data = yt.get_new_data(channel, opts, print_infos, force_all)

    else:  # rss
        data = rss.get_new_data(channel, opts, print_infos)
        data['addcount'] = -1

    if channel['mask']:
        apply_mask(data, channel['mask'])

    channel_add_missing_fields(data)
    return data


def get_video_data_only(url, opts, print_infos):
    if 'youtube' in url:
        data = yt.get_video_data_only(url, opts, print_infos)
    else:
        raise NotImplementedError(f'{url} is not yet supported for video only')

    channel_add_missing_fields(data)
    return data


def apply_mask(data, mask):
    regex = re.compile(mask)
    data['items'] = [medium for medium in data['items']
                     if regex.match(medium['title'])]
    return data


def update_medium(medium, print_infos):
    try:
        channel = medium['channel']
        channel_type = medium['channel']['type']
    except KeyError:
        channel = None
        channel_type = medium['type']
    if channel_type == 'youtube':
        updated = yt.update_medium(medium, print_infos)
    else:
        print('Not implemented on this type of channel')
        updated = False

    # Be sure we keep channel information
    if channel is not None:
        medium['channel'] = channel

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
    commandline = ('ffprobe -i "%s" -show_entries '
                   'format=duration -v quiet -of csv="p=0"' % filename)
    args = shlex.split(commandline)
    result = subprocess.Popen(
            args,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    output = result.communicate()
    duration = int(float(output[0]))
    return duration


def get_download_func(medium):
    backend = get_medium_backend(medium)
    return backend.download


def get_medium_backend(medium):
    return yt if medium['channel']['type'] == 'youtube' else rss


def get_filename(medium, backend, print_infos):
    ext = backend.get_filename_extension(medium)
    filename = str_to_filename(
        f'{ts_to_date(medium["date"])}_{medium["title"]}.{ext}')

    path = str_to_filename(medium['channel']['title'])
    filename = f'{path}/{filename}'

    return filename


class DownloadManager():
    def __init__(self, db, print_infos, wait=False, cb=noop):
        self.nthreads = 2
        self.print_infos = print_infos
        self.queue = Queue()
        self.wait = wait
        self.db = db
        self.cb = cb
        self.max_retries = 3
        self.cancel_requests = {}

        # Set up some threads to fetch the items to download
        for i in range(self.nthreads):
            worker = Thread(target=self.handle_queue)
            worker.daemon = True
            worker.start()

    def handle_queue(self):
        """This is the worker thread function. It processes items in the queue one
        after another.  These daemon threads go into an infinite loop, and only
        exit when the main thread ends."""
        q = self.queue

        # Wait for UI to be ready
        if not self.wait:
            sleep(2)

        while True:
            medium, cb = q.get()
            try:
                self.download(medium, cb)
                q.task_done()
            except DownloadError:
                if not medium['link'] in self.handle_queue.retries:
                    self.handle_queue.retries[medium['link']] = 1

                if (self.max_retries
                        <= self.handle_queue.retries[medium['link']]):
                    continue

                self.handle_queue.retries[medium['link']] += 1
                sleep(5)
                self.add(medium, update=False)
    handle_queue.retries = {}

    def add(self, medium, cb=noop, update=True):
        if update:
            self.print_infos('Add to download: %s' % medium['title'])
            medium['location'] = 'download'
            self.db.update_media([medium])

        if medium['link'] in self.cancel_requests:
            del self.cancel_requests[medium['link']]

        self.queue.put((medium, cb))

    def wait_done(self):
        self.queue.join()

    def download(self, medium, cb):
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
        backend = get_medium_backend(medium)
        dl_func = backend.download

        if medium['date'] == int(mktime(
                datetime.strptime('19700102', "%Y%m%d").timetuple())):
            backend.update_medium(medium, self.print_infos)

        filename = get_filename(medium, backend, self.print_infos)

        ret = multiprocessing.Queue()
        # Download needs to be done as a new process to be able to cancel it
        # XXX FIXME problem with print_infos in distributed memory!
        p = multiprocessing.Process(
            target=self.download_task,
            args=(ret, (dl_func, link, filename, self.print_infos)))
        p.daemon = True
        p.start()

        # While download is running, check if needs to be cancelled
        while p.is_alive():
            sleep(1)
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

        media = [medium]
        self.db.update_media(media)
        run_all(cb, ('modified', media))

    def download_task(self, ret, args):
        try:
            ret.put(args[0](*args[1:]))
        except DownloadError:
            exit(-1)

    def cancel_download(self, medium):
        self.cancel_requests[medium['link']] = True
        medium['location'] = 'remote'
        self.db.update_media([medium])


def search_media(search, source, print_infos, get_info=False, count=50):
    if source == 'youtube':
        items = yt.search_media(search, print_infos,
                                get_info=get_info, count=count)
    else:
        raise NotImplementedError('Not supported yet')

    for item in items:
        media_add_missing_fields(item, browse=True)
        item.setdefault('channel', {})['type'] = source

    return items


def get_mpv_config():
    mpv_config = {}
    mpv_config.update(yt.get_mpv_config())

    return mpv_config
