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
from collections import deque, Counter
from threading import Thread, Lock

import os.path

import termipod.backends as backends
import termipod.player as player
from termipod.database import DataBase, DataBaseUpdateException
from termipod.utils import (options_string_to_dict, commastr_to_list,
                            noop, run_all)
import termipod.config as Config
import termipod.playlist as Playlist
from termipod.database import DataBaseVersionException


class ItemListException(Exception):
    pass


class CallbackDeque(deque):
    def __init__(self, *args, **kwargs):
        self.callbacks = []
        super().__init__(*args, **kwargs)

    def extend(self, items):
        shift = len(self)
        for i, m in enumerate(items):
            m['index'] = shift+i
        super().extend(items)

        run_all(self.callbacks, ('new', items))

    def extendleft(self, items):
        shift = len(self)
        for i, m in enumerate(items):
            m['index'] = shift+len(items)-1-i
        super().extendleft(items)

        run_all(self.callbacks, ('new', items))


class ItemLists():
    def __init__(self, print_infos, wait=False, updatedb=False):
        self.db_name = Config.get('Global.db_path')
        self.wait = wait

        try:
            self.db = DataBase(self.db_name, print_infos, updatedb=updatedb)
        except DataBaseVersionException as e:
            raise ItemListException(e)

        self.print_infos = print_infos
        self.lastupdate = 0  # time of last channel update
        self.update_mutex = Lock()
        self.download_manager = None
        self.player = None

        # item lists
        self.media = CallbackDeque()
        self.channels = CallbackDeque()

        self.add_channels()
        self.add_media()

        # Mark removed files as read
        for medium in self.media:
            if ('local' == medium['location'] and
                    not os.path.isfile(medium['filename'])):
                self.remove_media([medium], unlink=False)

    def get_list(self, list_class, callback=noop):
        if list_class == 'media':
            itemlist = self.media

        elif list_class == 'channels':
            itemlist = self.channels

        elif list_class == 'browse':
            itemlist = CallbackDeque()

        itemlist.callbacks.append(callback)
        return itemlist

    def close_list(self, itemlist, callback=noop):
        itemlist.callbacks.remove(callback)
        if itemlist is self.media:
            pass
        elif itemlist is self.channels:
            pass
        elif not itemlist.callbacks:
            del itemlist

    def get_callbacks(self, itemlist):
        return itemlist.callbacks

    def media_update_index(self, media=None):
        if media is None:
            media = self.media
            start = 0
        else:
            start = len(self.media)

        for i, medium in enumerate(media):
            medium['index'] = start+i

    def channel_update_index(self, channels=None):
        if channels is None:
            channels = self.channels
            start = 0
        else:
            start = len(self.channels)

        for i, channel in enumerate(channels):
            channel['index'] = start+i

    def channel_get_categories(self):
        categories = Counter()
        for channel in self.channels:
            for category in channel['categories']:
                categories[category] += 1
        return categories

    def add_channels(self, channels=None, media=None):
        if channels is None:
            channels = self.db.select_channels()

        self.channel_update_index(channels)
        for i, c in enumerate(channels):
            c['media'] = deque()
            if media:
                c['media'].extendleft(media[i])
        self.channels.extend(channels)

        return channels

    def disable_channels(self, channel_ids, enable=False):
        channels = self.channel_ids_to_objects(channel_ids)
        for channel in channels:
            if enable:
                channel['disabled'] = False
            else:
                channel['disabled'] = True
            self.db.update_channel(channel)
        run_all(self.get_callbacks(self.channels), ('modified', channels))
        return channels

    def remove_channels(self, channel_ids, update_media=False):
        channels = self.channel_ids_to_objects(channel_ids)
        cids = [c['id'] for c in channels]
        self.db.channel_remove(cids)

        if update_media:
            # Count how many objects will be removed
            num_channel = len(cids)
            num_media = 0

            # Update channels and media
            media = []
            for channel in channels:
                channel_idx = self.channels.index(channel)
                del self.channels[channel_idx]
                mi_to_remove = [i for i, m in enumerate(self.media)
                                if m['channel']['id'] == channel['id']]
                mi_to_remove.sort(reverse=True)
                num_media += len(mi_to_remove)
                for mi in mi_to_remove:
                    media.append(self.media[mi])
                    del self.media[mi]

            self.media_update_index()
            self.channel_update_index()
            self.print_infos('%d channel(s) and %d media removed' %
                             (num_channel, num_media))
        else:
            self.print_infos(f'{len(cids)} channel(s) removed')

        run_all(self.get_callbacks(self.channels), ('removed', channels))
        run_all(self.get_callbacks(self.media), ('removed', media))
        return channels

    def add_media(self, media=None, update_channel=True):
        if media is None:
            for c in self.channels:
                c['media'] = deque()
            media = self.db.select_media()
            self.media.extendleft(media)
        else:
            media.reverse()
            self.media.extend(media)

        if update_channel:
            for m in media:
                m['channel']['media'].appendleft(m)

        return media

    def download_manager_init(self, dl_marked=False):
        if self.download_manager is None:
            self.download_manager = backends.DownloadManager(
                self.db, self.print_infos, wait=self.wait,
                cb=self.get_callbacks(self.media))

        if dl_marked:
            self.download_marked()

    def download_marked(self):
        for medium in self.media:
            if 'download' == medium['location']:
                self.download_manager.add(medium, update=False)
        if self.wait:
            self.wait_done()

    def download(self, itemlist, media):
        if self.download_manager is None:
            self.download_manager_init()

        for medium in media:
            if medium['location'] == 'remote':
                self.download_manager.add(medium,
                                          cb=self.get_callbacks(itemlist))
            elif medium['location'] == 'download':
                self.download_manager.cancel_download(medium)
            else:
                self.remove_media([medium], mark_as_read=False)

        run_all(self.get_callbacks(itemlist), ('modified', media))
        return media

    def player_init(self):
        self.player = player.Player(self, self.print_infos)

    def play(self, itemlist, media):
        if not media:
            return
        # Play first item
        medium = media[0]
        self.player.play(medium, cb=self.get_callbacks(self.media))
        # Enqueue next items
        self.playadd(media[1:])

    def playadd(self, itemlist, media):
        for medium in media:
            self.player.add(medium, cb=self.get_callbacks(self.media))

    def stop(self):
        self.player.stop()

    def switch_read(self, media, skip=False):
        updated_media = []
        original_media = []
        for original_medium in media:
            medium = original_medium.copy()

            if medium['state'] in ('read', 'skipped'):
                medium['state'] = 'unread'
            else:
                if skip:
                    medium['state'] = 'skipped'
                else:
                    medium['state'] = 'read'

            updated_media.append(medium)
            original_media.append(original_medium)

        try:
            self.update_media_data(original_media, updated_media)
        except DataBaseUpdateException:
            self.print_infos('Cannot update database with updated media',
                             mode='error')
            return []

        self.print_infos('All media marked')
        run_all(self.get_callbacks(self.media), ('modified', updated_media))

        return updated_media

    def update_media(self, media, itemlist):
        if itemlist is self.media:
            update_db = True
        else:
            update_db = False

        kwargs = {
            'update_db': update_db
        }
        threads = []
        enum_media = list(enumerate(media))
        nthreads = min(Config.get('Global.update_nthreads'), len(enum_media))
        for t in range(nthreads):
            args = (enum_media, len(media), itemlist)
            thread = Thread(target=self.update_media_task,
                            args=args, kwargs=kwargs)
            thread.daemon = True
            thread.start()
            threads.append(thread)

        if self.wait:
            for thread in threads:
                thread.join()

    def update_media_task(self, enum_media, size, itemlist, update_db=True):
        show_freq = 5
        updated_media = []
        original_media = []

        update_to_show = []
        while True:
            try:
                i, original_medium = enum_media.pop()
            except IndexError:
                run_all(self.get_callbacks(itemlist),
                        ("modified", update_to_show))
                break

            medium = original_medium.copy()

            self.print_infos(f'Update media {size-i}/{size}...')
            if backends.update_medium(medium, self.print_infos):
                updated_media.append(medium)
                original_media.append(original_medium)

                update_to_show.append(medium)
                if len(update_to_show) == show_freq:
                    run_all(self.get_callbacks(itemlist),
                            ("modified", update_to_show))
                    update_to_show = []

        try:
            self.update_media_data(original_media, updated_media,
                                   update_db=update_db)
            self.print_infos('Done updating media')
        except DataBaseUpdateException:
            self.print_infos('Cannot update database with updated media.',
                             mode='error')
            run_all(self.get_callbacks(itemlist), ("modified", original_media))

    def remove_media(self, media, unlink=True,
                     mark_as_read=True):
        if not media:
            return

        updated_media = []
        original_media = []

        for original_medium in media:
            medium = original_medium.copy()
            if unlink:
                if '' == medium['filename']:
                    self.print_infos('Filename is empty')

                elif os.path.isfile(medium['filename']):
                    try:
                        os.unlink(medium['filename'])
                    except FileNotFoundError:
                        self.print_infos(
                            f'Cannot remove {medium["filename"]}',
                            mode='error')
                    else:
                        self.print_infos(
                            f'File "{medium["filename"]}" removed',
                            mode='error')
                else:
                    self.print_infos(
                        f'File "{medium["filename"]}" is absent',
                        mode='error')

            if mark_as_read:
                medium['state'] = 'read'
            medium['location'] = 'remote'
            medium['filename'] = ''

            string = f'"{medium["title"]}" '
            if unlink:
                string += 'removed, '
            if mark_as_read:
                string += 'marked as read, '
            string += 'marked as remote.'
            self.print_infos(string)

            updated_media.append(medium)
            original_media.append(original_medium)

        try:
            self.update_media_data(original_media, updated_media)
            self.print_infos('Database updated')
        except DataBaseUpdateException:
            self.print_infos('Cannot update database with updated media',
                             mode='error')
            return []

        run_all(self.get_callbacks(self.media), ('modified', updated_media))
        return updated_media

    # Can raise DataBaseUpdateException
    def update_media_data(self, original_media, updated_media, update_db=True):
        if update_db:
            self.db.update_media(updated_media)
        for om, um in zip(original_media, updated_media):
            om.update(um)

    def apply_user_add_options(self, opts, sopts):
        if sopts:
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
            if 'auto' in uopts and not uopts['auto']:
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
        self.apply_user_add_options(opts, sopts)

        # Check not already present in db
        try:
            cleanurl = backends.get_clean_url(url)
        except ValueError as e:
            self.print_infos(e)
            return False

        channels = self.db.find_channels(cleanurl)
        channel_titles = [c['title'] for c in channels]
        if channels:
            if (not opts['force']
                    or not len(opts['name'])
                    or opts['name'] in channel_titles):
                channel = channels[0]
                self.print_infos(f'\"{channel["url"]}\" already present '
                                 f'({channel["title"]}). '
                                 'Use force=1 name=<new name>')
                return False

        self.print_infos(f'Add {url} ({opts["count"]} elements requested)')

        thread = Thread(target=self.new_channel_task,
                        args=(cleanurl, opts))
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
        data['disabled'] = False
        if opts['name']:
            data['title'] = opts['name']

        # Add channel to db
        media = self.db.add_channel(data)
        if media is None:
            return False

        self.add_channels([data], [media])
        self.add_media(media, update_channel=False)

        self.print_infos(f'{data["title"]} added ({len(media)} media)')

    def open_url(self, itemlist, url, sopts=None):
        opts = {
            'count': -1,
            'strict': 0,
        }
        self.apply_user_add_options(opts, sopts)

        self.print_infos(f'Open {url} ({opts["count"]} elements requested)')

        # Retrieve url feed
        opts['type'] = 'all'
        data = backends.get_all_data(url, opts, self.print_infos, browse=True)

        if data is None:
            return False

        media = data['items']
        if not media:
            return False

        for i, m in enumerate(media):
            m['channel'] = data
            m['index'] = len(itemlist)+i
        itemlist.extend(media)

        self.print_infos(f'{data["title"]} opened ({len(media)} media)')

        return media

    def new_video(self, url, sopts=None):
        opts = {
            'categories': '',
            'force': False,
            'name': ''
        }
        self.apply_user_add_options(opts, sopts)
        opts['auto'] = ''
        opts['mask'] = ''
        opts['count'] = 0
        opts['strict'] = 1

        try:
            data = backends.get_video_data_only(url, opts, self.print_infos)
        except NotImplementedError:
            self.print_infos(f'Unsupported address \"{url}\"')
            return False

        if opts['name']:
            data['title'] = opts['name']
        data['url'] = backends.get_clean_url(data['url'])

        # Check not already present in db
        channel = self.db.find_channel_by_name(data['title'])

        # Channel exists, video is added if force (and if missing)
        if channel:
            if not opts['force']:
                self.print_infos(f'\"{channel["title"]}\" already present. '
                                 'Use "force=1" to update it with the video')
                return False

            else:
                data['id'] = channel['id']
                new_media = self.db.add_media(data, force=True)
                if not new_media:
                    self.print_infos(f'\"{url}\" already present. ')
                    return False
                else:
                    self.add_media(new_media)
                    self.print_infos(
                        f'\"{channel["title"]}\" updated with video')
                    run_all(self.get_callbacks(self.channels),
                            ('modified', [channel]))

        # We create a new disabled channel
        else:
            data['categories'] = opts['categories']
            data['auto'] = opts['auto']
            data['mask'] = opts['mask']
            data['disabled'] = True

            # Add channel to db
            media = self.db.add_channel(data)
            if media is None:
                return False

            self.add_channels([data])
            self.add_media(media)

            self.print_infos(f'{data["title"]} added ({len(media)} media)')

    def channel_id_to_object(self, channel_id):
        if isinstance(channel_id, int):  # db cid
            channel = self.db.get_channel(channel_id)
            if channel is None:
                raise ValueError(f'Channel {channel_id} not found')

        elif isinstance(channel_id, dict):  # channel object
            channel = channel_id

        elif isinstance(channel_id, str):
            channel = self.db.find_channels(channel_id)
            if channel is None:
                raise ValueError(f'Channel {channel_id} not found')

        else:  # error
            raise ValueError('Bad channel id')

        return channel

    def channel_ids_to_objects(self, channel_ids):
        channels = []
        for c in channel_ids:
            found = self.channel_id_to_object(c)
            if isinstance(found, list):
                channels.extend(found)
            else:
                channels.append(found)
        return [c for c in channels if c is not None]

    def channel_object_to_id(self, channel):
        ids = [i for i in range(len(self.channels))
               if self.channels[i]['id'] == channel['id']]
        if len(ids) != 1:
            return None
        else:
            return ids[0]

    def channel_objects_to_ids(self, channels):
        ids = [i for i in (self.channel_object_to_id(c) for c in channels)
               if i is not None]
        return ids

    def channel_set_auto(self, channel_ids, auto=None):
        """ Switch auto value or set it to a value if argument auto is
        provided """
        channels = self.channel_ids_to_objects(channel_ids)
        for channel in channels:
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

        run_all(self.get_callbacks(self.channels), ('modified', channels))
        return channels

    def channel_set_categories(self, channel_ids, add_categories,
                               remove_categories):
        channels = self.channel_ids_to_objects(channel_ids)
        for channel in channels:
            add_category_str = ', '.join(list(add_categories))
            remove_category_str = ', '.join(list(remove_categories))

            channel['categories'] = set(channel['categories'])
            channel['categories'] -= remove_categories
            channel['categories'] |= add_categories
            channel['categories'] = list(channel['categories'])

            self.db.update_channel(channel)

        self.print_infos(f'Categories: add "{add_category_str}" '
                         f'remove "{remove_category_str}"')

        run_all(self.get_callbacks(self.channels), ('modified', channels))
        return channels

    def channel_set_mask(self, channel, mask):
        channel['mask'] = mask
        self.db.update_channel(channel)
        self.print_infos('Mask updated')

        run_all(self.get_callbacks(self.channels), ('modified', [channel]))
        return channel

    def update_channels(self, channel_ids=None, wait=False,
                        force_all=False):
        if channel_ids is None:
            channels = self.db.select_channels()
            channels = [c for c in channels if not c['disabled']]
        else:
            channels = self.channel_ids_to_objects(channel_ids)

        threads = []
        enum_channels = list(enumerate(channels))
        nchannels = len(channels)
        args = (enum_channels, nchannels)
        kwargs = {'force_all': force_all}

        ready = self.update_mutex.acquire(blocking=False)
        if not ready:
            # To prevent auto update from calling it again right away
            self.lastupdate = time.time()
            return False

        self.print_infos('Update...')

        for t in range(Config.get('Global.update_nthreads')):
            thread = Thread(target=self.update_channels_task,
                            args=args, kwargs=kwargs)
            thread.daemon = True
            thread.start()
            threads.append(thread)

        def release_mutex(threads):
            for thread in threads:
                thread.join()
            self.lastupdate = time.time()
            self.update_mutex.release()

        if self.wait:
            release_mutex(threads)

        else:
            thread = Thread(target=release_mutex, args=(threads,))
            thread.daemon = True
            thread.start()

    def update_channels_task(self, enum_channels, nchannels, force_all=False):
        new_media_num = 0
        updated_channels = []

        need_to_wait = False

        media_cb = self.get_callbacks(self.media)
        channel_cb = self.get_callbacks(self.channels)

        while True:
            try:
                i, channel = enum_channels.pop()
            except IndexError:
                break

            self.print_infos(f'Update channel {nchannels-i}/{nchannels} '
                             f'({channel["title"]})...')

            opts = {}
            data = backends.get_new_data(channel, opts, self.print_infos,
                                         force_all)

            data['id'] = channel['id']
            new_media = self.db.add_media(data, force=force_all)
            if not new_media:
                continue

            if force_all:
                # New media won't have all info, so we retrieve them
                updated_media = []
                original_media = []
                for original_medium in new_media:
                    medium = original_medium.copy()
                    if backends.update_media(medium, self.print_infos):
                        updated_media.append(medium)
                        original_media.append(original_medium)

                try:
                    self.update_media_data(original_media, updated_media)
                    run_all(self.get_callbacks(self.media),
                            ('modified', updated_media))
                except DataBaseUpdateException:
                    self.print_infos(
                        'Cannot update database with updated media',
                        mode='error')

            new_media_num += len(new_media)
            updated_channels.append(channel)

            # Automatic download
            if not '' == channel['auto']:
                regex = re.compile(channel['auto'])
                sub_media = [medium for medium in new_media
                             if regex.match(medium['title'])]
                if sub_media:
                    self.download_manager_init()
                    for s in sub_media:
                        self.download_manager.add(s)
                        need_to_wait = True
                    run_all(media_cb, ('modified', sub_media))

            new_media.sort(key=operator.itemgetter('date'), reverse=False)
            self.add_media(new_media)
            run_all(channel_cb, ('modified', updated_channels))

        if self.wait and need_to_wait:
            self.print_infos('Wait for downloads to complete...')
            self.download_manager.wait_done()

    def add_search_media(self, itemlist, search, source, count=30):
        media = backends.search_media(search, source, self.print_infos,
                                      count=count)
        if not media:
            return

        itemlist.extend(media)
        self.print_infos(f'Search done ({len(media)} media added)!')
        return media

    def add_playlist_media(self, itemlist, name):
        media = Playlist.to_media(name)

        if not media:
            return

        itemlist.extend(media)
        self.print_infos(f'Playlist read ({len(media)} media added)!')
        return media

    def add_to_other_itemlist(self, dst_itemlist, src_media):
        media = [m.copy() for m in src_media]

        dst_itemlist.extend(media)
        self.print_infos(f'Sent to playlist ({len(media)} media added)!')
        return media

    def export_channels(self):
        exports = []
        for c in self.channels:
            export = '%s - %s' % (c['url'], c['title'])
            if c['disabled']:
                export = '# '+export
            exports .append(export)
        return '\n'.join(exports)

    def medium_get_tags(self):
        tags = Counter()
        for medium in self.media:
            for tag in medium['tags']:
                tags[tag] += 1
        return tags

    def medium_set_tags(self, media, add_tags,
                        remove_tags):
        updated_media = []
        original_media = []
        for original_medium in media:
            medium = original_medium.copy()
            updated_media.append(medium)
            original_media.append(original_medium)

            add_tag_str = ', '.join(list(add_tags))
            remove_tag_str = ', '.join(list(remove_tags))

            medium['tags'] = set(medium['tags'])
            medium['tags'] -= remove_tags
            medium['tags'] |= add_tags
            medium['tags'] = list(medium['tags'])

        try:
            self.update_media_data(original_media, updated_media)
        except DataBaseUpdateException:
            self.print_infos('Cannot update database with updated media',
                             mode='error')
            return []

        self.print_infos(f'tags: add "{add_tag_str}" '
                         f'remove "{remove_tag_str}"')

        run_all(self.get_callbacks(self.media), ('modified', updated_media))
        return updated_media
