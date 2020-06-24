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
from threading import Thread
import errno
import stat
import itertools
import atexit

try:
    import pyfuse3
    from pyfuse3 import Operations as FuseOperations
    import trio
    _has_fuse = True
except ModuleNotFoundError:
    _has_fuse = False
    FuseOperations = object

from termipod.backends import shrink_link, is_channel_url
import termipod.config as Config

from termipod.cache import item_get_cache
from termipod.utils import str_to_filename, str_to_short_hash

try:
    import faulthandler
except ImportError:
    pass
else:
    faulthandler.enable()


class StartException(Exception):
    pass


def get_item_by_field(itemlist, field, value):
    return next((item for item in itemlist if item[field] == value),
                None)


def get_items_by_field(itemlist, field, value):
    return (item for item in itemlist if item[field] == value)


def get_categories():
    return ['TODO', 'XXX', 'FIXME']


class Operations(FuseOperations):
    enable_writeback_cache = True
    readme = """
- You can open media files as normal files to read them
- You can interact with termipod using file operations
  - For media
    - Mark a file as read: rm <medium file>
    - Update a medium: touch <medium file>
  - For channels
    - To add a channel: mkdir <URL>
    """

    def __init__(self, itemlists):
        self.itemlists = itemlists
        self.channels = itemlists.channels
        self.media = itemlists.media
        """
        - /
            - ## channels ##
                - channel_name
                    - medium
            - ## tags ##
                - tag_name
                    - medium
            - ## media ##
                - last 7 days
                    - medium
        """
        self.inodes = [
            {},
            {'type': 'root', 'name': 'root'},
        ]
        self.inode_table = {}
        self.file_handles = []

        self.maindirs = [proxy_base, 'channels', 'media', 'search']
        for d in self.maindirs:
            self.get_inode(1, d, d, None)

        self.proxy_inode = self.inode_table[1, proxy_base]
        self.media_inode = self.inode_table[1, 'media']
        self.channels_inode = self.inode_table[1, 'channels']

        for m in self.media:
            self.medium_get_inode(self.media_inode, m)

        for c in self.channels:
            inode_p, _ = self.channel_get_inode(self.channels_inode, c)
            for m in c['media']:
                self.medium_get_inode(inode_p, m)

        super(Operations, self).__init__()

    def channel_get_inode(self, inode_p, channel):
        title = channel['title']
        inode = self.get_inode(inode_p, title, 'channel', channel)

        return inode, title

    def medium_build_filename(self, medium, inode_p):
        parent_type = self.inodes[inode_p]['type']

        h = shrink_link(medium['channel'], medium['link'])
        if len(h) > 15:
            h = str_to_short_hash(medium['link'])

        name = ''
        if medium['state'] == 'read':
            name = '.'
        elif medium['state'] == 'skipped':
            name = '..'

        if parent_type != 'channel':
            name += f'{medium["channel"]["title"]} -- '

        name += f'{medium["title"]}.{h}.mp4'

        return str_to_filename(name)

    def medium_get_inode(self, inode_p, medium):
        title = self.medium_build_filename(medium, inode_p)
        inode = self.get_inode(inode_p, title, 'medium', medium)

        return inode, title

    def invalidate_inode(self, inode):
        try:
            del self.inodes[inode]['attr']
        except KeyError:
            pass
        pyfuse3.invalidate_inode(inode, attr_only=True)

        inode_p = self.inodes[inode]['inode_p']
        try:
            del self.inodes[inode_p]['attr']
        except KeyError:
            pass

        # Invalidate parent inode
        # name = self.inodes[inode]['name']
        # try:
        #     pyfuse3.invalidate_entry(inode_p, name.encode())
        # except FileNotFoundError:  # If already invalidated by other open
        #     pass

    def create_inode_raw(self, item_type, inode_p, name, value):
        inode = len(self.inodes)
        self.inodes.append({
            'type': item_type,
            'inode': inode,
            'inode_p': inode_p,
            'name': name,
            'value': value,
        })
        return inode

    def get_inode(self, inode_p, name, item_type=None, item=None):
        try:
            inode = self.inode_table[inode_p, name]

        except KeyError:
            if item_type is None:
                raise(pyfuse3.FUSEError(errno.ENOENT))

            inode = self.create_inode_raw(item_type, inode_p, name, item)
            self.inode_table[inode_p, name] = inode
        return inode

    def url_get_complete(self, inode_p, name):
        tokens = [name]
        while True:
            inode_entry = self.inodes[inode_p]
            if inode_entry['type'] == 'channels':
                if tokens[-1].endswith(':'):
                    tokens[-1] += '/'
                break

            elif inode_entry['type'] == 'url':
                tokens.append(inode_entry['name'])
                inode_p = inode_entry['inode_p']

            else:
                raise ValueError

        url = '/'.join(list(tokens[::-1]))
        if is_channel_url(url):
            return url
        else:
            return ''

    def url_get_inode(self, inode_p, name):
        try:
            if not self.url_get_complete(inode_p, name):
                return self.get_inode(inode_p, name, 'url', None)
            else:
                raise(pyfuse3.FUSEError(errno.ENOENT))
        except ValueError:
            raise(pyfuse3.FUSEError(errno.ENOENT))

    async def lookup(self, inode_p, name, ctx=None):
        name = name.decode().lstrip('.')
        if self.inodes[inode_p]['type'] == 'channels':
            channel = get_item_by_field(self.channels, 'title', name)
            if channel is None:
                # Can be a lookup from a mkdir to add channel with url split
                # into parts
                inode = self.url_get_inode(inode_p, name)

            else:
                inode, title = self.channel_get_inode(inode_p, channel)

        elif self.inodes[inode_p]['type'] == 'search':
            # TODO
            raise(pyfuse3.FUSEError(errno.ENOENT))

        elif self.inodes[inode_p]['type'] == 'url':
            inode = self.url_get_inode(inode_p, name)

        else:
            inode = self.get_inode(inode_p, name)

        return await self.getattr(inode, ctx)

    def get_item(self, inode):
        return self.inodes[inode]

    def medium_generate_m3u(self, medium):
        m3u_data = b'#EXTM3U\n%s\n' % medium['link'].encode()
        return m3u_data

    async def getattr(self, inode, ctx=None):
        item = self.get_item(inode)

        try:
            return self.inodes[inode]['attr']
        except KeyError:
            pass

        atime = 0
        ctime = 0
        mtime = 0
        size = 0
        file_type = stat.S_IFDIR

        if item['type'] == 'channels':
            file_type = stat.S_IFDIR
            size = len(self.channels)

        elif item['type'] == 'channel':
            channel = item['value']
            date = channel['updated']*10**9
            try:
                last_medium_date = channel['media'][-1]['date']*10**9
            except IndexError:
                last_medium_date = 0

            file_type = stat.S_IFDIR
            size = len(item['value']['media'])
            ctime = date
            mtime = last_medium_date

        elif item['type'] == 'medium':
            medium = item['value']

            item['target'] = f'{proxy_dir}/{item["name"]}'
            # Creation of the cache inode
            self.get_inode(self.proxy_inode, item['name'], item_type='cache',
                           item=item)

            date = medium['date']*10**9

            size = medium['duration']
            file_type = stat.S_IFLNK
            ctime = date
            mtime = date

        elif item['type'] == 'cache':
            medium = item['value']['value']
            file_type = stat.S_IFREG

            cache_fn = item_get_cache(medium, 'link', print_infos,
                                      check_only=True)
            if download:
                if cache_fn:
                    size = os.path.getsize(cache_fn)
                else:
                    size = 0
            else:
                item['file_data'] = self.medium_generate_m3u(medium)
                size = len(item['file_data'])

        entry = pyfuse3.EntryAttributes()
        entry.st_ino = inode
        entry.generation = 0
        entry.entry_timeout = 300
        entry.attr_timeout = 300
        entry.st_mode = (file_type | stat.S_IRUSR | stat.S_IWUSR
                         | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP
                         | stat.S_IROTH | stat.S_IXOTH)
        entry.st_nlink = 1

        entry.st_uid = os.getuid()
        entry.st_gid = os.getgid()

        entry.st_rdev = 0
        entry.st_size = size

        entry.st_blksize = 512
        entry.st_blocks = 1
        entry.st_atime_ns = atime
        entry.st_mtime_ns = mtime
        entry.st_ctime_ns = ctime

        self.inodes[inode]['attr'] = entry

        return entry

    async def opendir(self, inode, ctx):
        return inode

    async def readdir(self, inode, off, token):
        data = self.inodes[inode]

        if data['type'] == 'root':
            enum_dirs = list(enumerate(self.maindirs))
            for i, d in enum_dirs[off:]:
                inode_c = self.inode_table[inode, d]
                pyfuse3.readdir_reply(token, d.encode(),
                                      await self.getattr(inode_c), i+1)

        elif data['type'] == 'channels':
            enum_channels = list(enumerate(self.channels))
            for i, channel in enum_channels[off:]:
                inode_c, title = self.channel_get_inode(inode, channel)
                pyfuse3.readdir_reply(token, title.encode(),
                                      await self.getattr(inode_c), i+1)

        elif data['type'] == 'media':
            nmedia = len(self.media)
            media = list(itertools.islice(self.media,
                                          max(nmedia-max_media, 0), nmedia))

            enum_media = list(enumerate(media))
            for i, medium in enum_media[off:]:
                inode_c, title = self.medium_get_inode(inode, medium)
                pyfuse3.readdir_reply(token, title.encode(),
                                      await self.getattr(inode_c), i+1)

        elif data['type'] == 'search':
            raise NotImplementedError

        elif data['type'] == 'channel':
            channel = data['value']
            nmedia = len(channel['media'])
            media = list(itertools.islice(channel['media'],
                                          max(nmedia-max_media, 0), nmedia))

            enum_media = list(enumerate(media))
            for i, medium in enum_media[off:]:
                inode_c, title = self.medium_get_inode(inode, medium)
                pyfuse3.readdir_reply(token, title.encode(),
                                      await self.getattr(inode_c), i+1)

        elif data['type'] == '.proxies':
            # Find all proxies
            inodes = [v for k, v in self.inode_table.items()
                      if k[0] == self.proxy_inode]
            for i, inode_c in list(enumerate(inodes))[off:]:
                item = self.inodes[inode_c]
                pyfuse3.readdir_reply(token, item['name'].encode(),
                                      await self.getattr(inode_c), i+1)

    async def unlink(self, inode_p, name, ctx):
        name = name.decode().lstrip('.')
        inode = self.inode_table[inode_p, name]
        item = self.inodes[inode]

        if item['type'] == 'medium':
            medium = item['value']
            self.itemlists.switch_read([medium])
        else:
            raise(NotImplementedError)

    async def readlink(self, inode, ctx):
        item = self.get_item(inode)
        return item['target'].encode()

    async def rmdir(self, inode_p, name, ctx):
        name = name.decode().lstrip('.')
        raise(NotImplementedError)

    async def rename(self, inode_p_old, name_old, inode_p_new, name_new,
                     flags, ctx):
        name = name.decode().lstrip('.')
        raise(NotImplementedError)

    async def setattr(self, inode, attr, fields, fh, ctx):
        return await self.getattr(inode)

    async def mkdir(self, inode_p, name, mode, ctx):
        name = name.decode()
        url = self.url_get_complete(inode_p, name)
        if url:
            sopts = 'count=30'
            self.itemlists.new_channel(url, sopts=sopts)
            inode = self.get_inode(inode_p, name, 'url', None)
            return await self.getattr(inode)

    async def statfs(self, ctx):
        stat_ = pyfuse3.StatvfsData()

        stat_.f_bsize = 512
        stat_.f_frsize = 512

        size = len(self.media)
        stat_.f_blocks = size // stat_.f_frsize
        stat_.f_bfree = max(size // stat_.f_frsize, 1024)
        stat_.f_bavail = stat_.f_bfree

        inodes = len(self.inodes)
        stat_.f_files = inodes
        stat_.f_ffree = max(inodes, 100)
        stat_.f_favail = stat_.f_ffree

        return stat_

    async def open(self, inode, flags, ctx):
        item = self.inodes[inode]
        if item['type'] != 'cache':
            raise(pyfuse3.FUSEError(errno.EISDIR))

        medium = item['value']['value']
        if download:
            cache_fn = item_get_cache(medium, 'link', print_infos)
            if not cache_fn:
                raise(pyfuse3.FUSEError(errno.ENODATA))
            file = open(cache_fn, 'br')

            # To have the right size for the opener (not 0)
            size = file.seek(0, os.SEEK_END)
            before_end = file.seek(size-1, os.SEEK_SET)
            pyfuse3.notify_store(inode, before_end, file.read(1))
            file.seek(0, os.SEEK_SET)
            # try:
            #     if not item['attr'].st_size:
            #         self.invalidate_inode(inode)
            #         self.invalidate_inode(item['value']['inode'])
            # except KeyError:
            #     pass

            fh = len(self.file_handles)
            self.file_handles.append({
                'type': 'file',
                'value': file,
            })

        else:
            # Not needed to have fh here but simpler to go with
            # 'download' case
            fh = len(self.file_handles)
            self.file_handles.append({
                'type': 'data',
                'value': item['file_data'],
            })

        return pyfuse3.FileInfo(fh=fh)

    async def access(self, inode, mode, ctx):
        return True

    # async def create(self, inode_parent, name, mode, flags, ctx):
    #     raise(NotImplementedError)

    async def read(self, fh, offset, length):
        item = self.file_handles[fh]
        if item['type'] == 'data':
            return item['value'][offset:offset+length]

        elif item['type'] == 'file':
            file = item['value']
            file.seek(offset)
            return file.read(length)

        else:
            raise(pyfuse3.FUSEError(errno.ENODATA))

    # async def write(self, fh, offset, buf):
    #     raise(NotImplementedError)

    async def release(self, fh):
        item = self.file_handles[fh]

        if item['type'] == 'file':
            file = item['value']
            file.close()

        del item
        self.file_handles[fh] = None

    def get_readme_data(self, offset, length):
        return self.readme[offset:offset+length]


def run_fuse():
    try:
        trio.run(pyfuse3.main)
    except:
        pyfuse3.close(unmount=False)
        raise

    pyfuse3.close()


@atexit.register
def stop_fuse():
    if fuse_started:
        os.system(f'fusermount -zu {mountpoint}')


def init(itemlists, printf):
    global print_infos
    print_infos = printf

    if not _has_fuse:
        print_infos(
            "To have fuse FS you need to install 'pyfuse3' and/or 'trio'",
            mode='error'
        )
        return

    if not os.path.exists(mountpoint):
        try:
            os.makedirs(mountpoint)
        except FileExistsError:
            raise StartException(f'You need to unmount {mountpoint} first')

    operations = Operations(itemlists)

    fuse_options = set(pyfuse3.default_options)
    fuse_options.add('fsname=termipod')
    fuse_options.discard('default_permissions')
    # fuse_options.add('debug')
    try:
        pyfuse3.init(operations, mountpoint, fuse_options)
    except RuntimeError as e:
        raise StartException(e)

    thread = Thread(target=run_fuse)
    thread.daemon = True
    thread.start()

    global fuse_started
    fuse_started = True


fuse_started = False
mountpoint = os.path.realpath('__termifuse__')
proxy_base = '.proxies'
proxy_dir = f'{mountpoint}/{proxy_base}'
print_infos = None
download = Config.get('Global.fuse_download_media')
max_media = Config.get('Global.fuse_nmedia')
