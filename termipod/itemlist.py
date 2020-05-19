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
import re
import operator
import os
import time
from threading import Thread, Lock

import os.path

import termipod.backends as backends
import termipod.player as player
from termipod.database import DataBase, DataBaseUpdateException
from termipod.utils import options_string_to_dict, commastr_to_list


class ItemList():
    def __init__(self, config, print_infos, wait=False, updatedb=False):
        self.db_name = config.db_path
        self.wait = wait
        self.db = DataBase(self.db_name, print_infos, updatedb=updatedb)
        self.print_infos = print_infos
        self.medium_areas = []
        self.channel_areas = []
        self.media = []
        self.channels = []
        self.lastupdate = 0  # time of last channel update
        self.update_mutex = Lock()

        self.add_channels()
        self.add_media()

        self.player = player.Player(self, self.print_infos)
        self.download_manager = \
            backends.DownloadManager(self, self.print_infos, wait=self.wait)

        # Mark removed files as read
        for medium in self.media:
            if 'local' == medium['location'] and \
                    not os.path.isfile(medium['filename']):
                self.remove(medium=medium, unlink=False)

    def media_update_index(self):
        for i, medium in enumerate(self.media):
            medium['index'] = i

    def channel_update_index(self):
        for i, channel in enumerate(self.channels):
            channel['index'] = i

    def channel_get_categories(self):
        categories = set()
        for channel in self.channels:
            categories |= set(channel['categories'])
        return categories

    def add_channels(self, channels=None):
        if channels is None:
            channels = self.db.select_channels()

        self.channels[0:0] = channels
        self.channel_update_index()
        self.update_channel_areas()  # TODO smart

    def disable_channels(self, origin, channel_ids):
        channels = self.channel_ids_to_objects(origin, channel_ids)
        for channel in channels:
            channel['disabled'] = True
            self.db.update_channel(channel)

    def remove_channels(self, origin, channel_ids):
        channels = self.channel_ids_to_objects(origin, channel_ids)
        cids = [c['id'] for c in channels]
        self.db.channel_remove(cids)

        # Count how many objects will be removed
        num_channel = len(cids)
        num_media = 0

        # Update channels and media
        for channel in channels:
            channel_idx = self.channels.index(channel)
            del self.channels[channel_idx]
            mi_to_remove = [i for i, m in enumerate(self.media)
                            if m['channel']['id'] == channel['id']]
            mi_to_remove.sort(reverse=True)
            num_media += len(mi_to_remove)
            for mi in mi_to_remove:
                del self.media[mi]

        self.media_update_index()
        self.channel_update_index()
        self.print_infos('%d channel(s) and %d media removed' %
                         (num_channel, num_media))

    def add_medium_area(self, area):
        self.medium_areas.append(area)

    def add_channel_area(self, area):
        self.channel_areas.append(area)

    def add_media(self, media=None):
        if media is None:
            self.media = []
            media = self.db.select_media()

        self.media[0:0] = media
        self.media_update_index()

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
            if medium['location'] == 'remote':
                self.download_manager.add(medium)
            elif medium['location'] == 'download':
                self.download_manager.cancel_download(medium)
            else:
                self.remove(medium=medium, mark_as_read=False)
            media.append(medium)

    def play(self, indices):
        if not len(indices):
            return
        # Play first item
        idx = indices[0]
        medium = self.media[idx]
        self.player.play(medium)
        # Enqueue next items
        self.playadd(indices[1:])

    def playadd(self, indices):
        for idx in indices:
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
            try:
                self.db.update_medium(medium)
                media.append(medium)
            except DataBaseUpdateException:
                self.print_infos('Update media failed!', mode='error')

        self.update_medium_areas(modified_media=media)

    def update_media(self, indices, skip=False):
        if isinstance(indices, int):
            indices = [indices]

        media = []
        nfailed = 0
        i = 1
        for idx in indices:
            self.print_infos(f'Update media {i}/{len(indices)}...')
            medium = self.media[idx]
            if medium['duration'] == 0:
                if backends.update_medium(medium, self.print_infos):
                    try:
                        self.db.update_medium(medium)
                        media.append(medium)
                        i += 1
                    except DataBaseUpdateException:
                        nfailed += 1

        self.update_medium_areas(modified_media=media)
        self.print_infos(
            'Update media done' +
            f' ({nfailed} failed)' if nfailed else '')

    def remove(self, idx=None, medium=None, unlink=True, mark_as_read=True):
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
        if mark_as_read:
            medium['state'] = 'read'
        medium['location'] = 'remote'
        medium['filename'] = ''

        try:
            self.db.update_medium(medium)
            self.update_medium_areas(modified_media=[medium])
        except DataBaseUpdateException:
            self.print_infos('Update media failed!')

    def new_channel(self, url, sopts=None):
        opts = {
            'count': -1,
            'strict': 0,
            'auto': '',
            'categories': '',
            'mask': '',
            'force': False,
            'name': ''
        }

        if sopts is not None and len(sopts):
            try:
                uopts = options_string_to_dict(sopts, opts.keys())
            except ValueError as e:
                self.print_infos(e)
                return False

            if 'count' in uopts:
                uopts['count'] = int(uopts['count'])
            if 'strict' in uopts:
                uopts['strict'] = (
                    1 if not uopts['strict'] else
                    int(uopts['strict']))
            if 'auto' in uopts and not len(uopts['auto']):
                uopts['auto'] = '.*'
            if 'force' in uopts:
                uopts['force'] = (
                    1 if not uopts['force'] else
                    int(uopts['force']))
            if 'categories' in uopts:
                uopts['categories'] = (
                    commastr_to_list(uopts['categories']))

            # Merge options
            opts.update(uopts)

        # Check not already present in db
        cleanurl = backends.get_clean_url(url)
        if not cleanurl:
            self.print_infos(f'Unsupported address \"{url}\"')
            return False

        channels = self.db.find_channels(cleanurl)
        channel_titles = [c['title'] for c in channels]
        if channels:
            if not opts['force'] \
                    or not len(opts['name']) \
                    or opts['name'] in channel_titles:
                channel = channels[0]
                self.print_infos(f'\"{channel["url"]}\" already present '
                                 f'({channel["title"]}). '
                                 'Use force=1 name=<new name>')
                return False

        self.print_infos(f'Add {url} ({opts["count"]} elements requested)')

        thread = Thread(target=self.new_channel_task, args=(cleanurl, opts))
        thread.daemon = True
        thread.start()
        if self.wait:
            thread.join()

    def new_channel_task(self, url, opts):
        # Retrieve url feed
        data = backends.get_all_data(url, opts, self.print_infos)

        if data is None:
            return False

        data['categories'] = opts['categories']
        data['auto'] = opts['auto']
        data['mask'] = opts['mask']
        data['disabled'] = 0
        if opts['name']:
            data['title'] = opts['name']

        # Add channel to db
        media = self.db.add_channel(data)
        if media is None:
            return False

        self.add_channels([data])
        self.add_media(media)

        self.print_infos(f'{data["title"]} added ({len(media)} media)')

    def medium_idx_to_object(self, idx):
        return self.media[idx]

    def medium_idx_to_objects(self, idx):
        medium = [self.medium_idx_to_object(c) for c in idx]
        return [c for c in medium if c is not None]

    def channel_id_to_object(self, origin, channel_id):  # TODO XXX oops
        if origin == 'ui':
            channel = self.channels[channel_id]
        elif isinstance(channel_id, int):  # db cid
            channel = self.db.get_channel(channel_id)
            if channel is None:
                self.print_infos('Channel "%s" not found' % channel_id)
        elif isinstance(channel_id, dict):  # channel object
            channel = channel_id
        else:  # error
            channel = None
        return channel

    def channel_ids_to_objects(self, origin, channel_ids):
        channels = [self.channel_id_to_object(origin, c) for c in channel_ids]
        return [c for c in channels if c is not None]

    def channel_set_auto(self, origin, channel_ids, auto=None):
        """ Switch auto value or set it to a value if argument auto is
        provided """
        for channel_id in channel_ids:
            channel = self.channel_id_to_object(origin, channel_id)
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

            self.db.update_channel(channel)

        self.update_channel_areas()

    def channel_set_categories(self, origin, channel_ids, add_categories,
                               remove_categories):
        for channel_id in channel_ids:
            channel = self.channel_id_to_object(origin, channel_id)

            add_category_str = ', '.join(list(add_categories))
            remove_category_str = ', '.join(list(remove_categories))

            channel['categories'] = set(channel['categories'])
            channel['categories'] -= remove_categories
            channel['categories'] |= add_categories
            channel['categories'] = list(channel['categories'])

            self.db.update_channel(channel)

        self.print_infos(f'Categories: add "{add_category_str}" '
                         f'remove "{remove_category_str}"')

        self.update_channel_areas()

    def update_channels(self, origin, channel_ids=None, wait=False):
        if channel_ids is None:
            channels = self.db.select_channels()
            channels = [c for c in channels if not c['disabled']]
        else:
            channels = self.channel_ids_to_objects(origin, channel_ids)

        if wait or self.wait:
            self.update_task(channels)
        else:
            thread = Thread(target=self.update_task, args=(channels, ))
            thread.daemon = True
            thread.start()

    def update_task(self, channels):
        ready = self.update_mutex.acquire(blocking=False)
        if not ready:
            # To prevent auto update from calling it again right away
            self.lastupdate = time.time()
            return False

        self.print_infos('Update...')

        all_new_media = []

        need_to_wait = False
        for i, channel in enumerate(channels):
            self.print_infos(f'Update channel {i+1}/{len(channels)} '
                             f'({channel["title"]})...')

            opts = {}
            data = backends.get_new_data(channel, opts, self.print_infos)

            data['id'] = channel['id']
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

        self.lastupdate = time.time()
        self.update_mutex.release()

        if self.wait and need_to_wait:
            self.print_infos('Wait for downloads to complete...')
            self.download_manager.wait_done()

    def export_channels(self):
        exports = []
        for c in self.channels:
            export = '%s - %s' % (c['url'], c['title'])
            if c['disabled']:
                export = '# '+export
            exports .append(export)
        return '\n'.join(exports)
