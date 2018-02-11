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
import operator
import os
from threading import Thread

import os.path

import termipod.backends as backends
import termipod.player as player
from termipod.database import DataBase
from termipod.utils import *


class ItemList():
    def __init__(self, config, print_infos=print, wait=False):
        self.db_name = config.db_path
        self.wait = wait
        self.db = DataBase(self.db_name, print_infos)
        self.print_infos = print_infos
        self.medium_areas = []
        self.channel_areas = []
        self.media = []
        self.channels = []

        self.add_channels()
        self.add_media()

        self.player = player.Player(self, self.print_infos)
        self.download_manager = \
            backends.DownloadManager(self, self.wait, self.print_infos)

        # Mark removed files as read
        for medium in self.media:
            if 'local' == medium['location'] and \
                    not os.path.isfile(medium['filename']):
                self.remove(medium=medium, unlink=False)

    def add_channels(self, channels=None):
        if channels is None:
            channels = self.db.select_channels()

        self.channels[0:0] = channels
        for i, c in enumerate(self.channels):
            c['index'] = i
        self.update_channel_areas()  # TODO smart

    def add_medium_area(self, area):
        self.medium_areas.append(area)

    def add_channel_area(self, area):
        self.channel_areas.append(area)

    def add_media(self, media=None):
        if media is None:
            self.media = []
            media = self.db.select_media()

        self.media[0:0] = media
        for i, v in enumerate(self.media):
            v['index'] = i

        self.update_medium_areas(new_media=media)

    def update_medium_areas(self, new_media=None, modified_media=None):
        for area in self.medium_areas:
            if new_media is None and modified_media is None:
                area.reset_contents()
            else:
                if new_media is not None:
                    area.add_contents(new_media)
                if modified_media is not None:
                    area.update_contents(modified_media)

    def update_channel_areas(self):
        for area in self.channel_areas:
                area.reset_contents()

    def add(self, medium):
        self.media.append(medium)
        self.update_strings()

    def download(self, indices):
        if isinstance(indices, int):
            indices = [indices]

        media = []
        for idx in indices:
            medium = self.media[idx]
            link = medium['link']

            channel = self.db.get_channel(medium['url'])
            self.download_manager.add(medium, channel)
            media.append(medium)

    def play(self, idx):
        medium = self.media[idx]
        self.player.play(medium)

    def playadd(self, idx):
        medium = self.media[idx]
        self.player.add(medium)

    def stop(self):
        self.player.stop()

    def switch_read(self, indices, skip=False):
        if isinstance(indices, int):
            indices = [indices]

        media = []
        for idx in indices:
            medium = self.media[idx]
            if medium['state'] in ('read', 'skipped'):
                medium['state'] = 'unread'
            else:
                if skip:
                    medium['state'] = 'skipped'
                else:
                    medium['state'] = 'read'
            self.db.update_medium(medium)
            media.append(medium)

        self.update_medium_areas(modified_media=media)

    def remove(self, idx=None, medium=None, unlink=True):
        if idx:
            medium = self.media[idx]

        if not medium:
            return

        if unlink:
            if '' == medium['filename']:
                self.print_infos('Filename is empty')

            elif os.path.isfile(medium['filename']):
                try:
                    os.unlink(medium['filename'])
                except FileNotFoundError:
                    self.print_infos('Cannot remove "%s"' % medium['filename'])
                else:
                    self.print_infos('File "%s" removed' % medium['filename'])
            else:
                self.print_infos('File "%s" is absent' % medium['filename'])

        self.print_infos('Mark "%s" as local and read' % medium['title'])
        medium['state'] = 'read'
        medium['location'] = 'remote'
        self.db.update_medium(medium)

        self.update_medium_areas(modified_media=[medium])

    def new_channel(self, url, auto='', genre=''):
        self.print_infos('Add '+url)
        # Check not already present in db
        channel = self.db.get_channel(url)
        if channel is not None:
            self.print_infos('"%s" already present (%s)' %
                             (channel['url'], channel['title']))
            return False

        thread = Thread(target=self.new_channel_task, args=(url, genre, auto))
        thread.daemon = True
        thread.start()
        if self.wait:
            thread.join()

    def new_channel_task(self, url, genre, auto):
        # Retrieve url feed
        data = backends.get_data(url, self.print_infos, True)

        if data is None:
            return False

        # Add channel to db
        data['genre'] = genre
        data['auto'] = auto
        updated = data['updated']
        data['updated'] = 0  # set to 0 in db for add_media
        self.db.add_channel(data)
        data['updated'] = updated

        # Update medium list
        media = self.db.add_media(data)

        self.add_channels([data])
        self.add_media(media)

        self.print_infos(data['title']+' added')

    def channel_auto(self, idx, auto=None):
        """ Switch auto value or set it to a value if argument auto is
        provided """
        channel = self.channels[idx]
        title = channel['title']

        if auto is None:
            if '' == channel['auto']:
                new_value = '.*'
            else:
                new_value = ''
        else:
            new_value = auto
        channel['auto'] = new_value
        self.print_infos('Auto for channel %s is set to: "%s"' %
                         (title, new_value))

        self.update_channel_areas()
        self.db.update_channel(channel)

    def update_medium_list(self, urls=None):
        self.print_infos('Update...')
        if urls is None:
            urls = list(map(lambda x: x['url'], self.db.select_channels()))

        thread = Thread(target=self.update_task, args=(urls, ))
        thread.daemon = True
        thread.start()
        if self.wait:
            thread.join()

    def update_task(self, urls):
        all_new_media = []

        need_to_wait = False
        for i, url in enumerate(urls):
            channel = self.db.get_channel(url)
            self.print_infos('Update channel %s (%d/%d)...' %
                             (channel['title'], i+1, len(urls)))

            data = backends.get_data(url, self.print_infos)

            if data is None:
                continue

            new_media = self.db.add_media(data)
            if not new_media:
                continue

            all_new_media = new_media+all_new_media

            # Automatic download
            if not '' == channel['auto']:
                regex = re.compile(channel['auto'])
                sub_media = [medium for medium in new_media
                             if regex.match(medium['title'])]
                for s in sub_media:
                    self.download_manager.add(s, channel)
                    need_to_wait = True
        self.print_infos('Update channels done!')

        all_new_media.sort(key=operator.itemgetter('date'), reverse=True)
        self.add_media(all_new_media)

        if self.wait and need_to_wait:
            self.print_infos('Wait for downloads to complete...')
            self.download_manager.wait_done()
