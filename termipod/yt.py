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
from datetime import datetime
from time import mktime, time
from threading import Thread

import feedparser as fp
import youtube_dl as ytdl

from termipod.utils import printable_str
from termipod.backends_exceptions import DownloadError
import termipod.config as Config
# printable_str = print


class DownloadLogger(object):
    def __init__(self, print_infos, url):
        self.print_infos = print_infos
        self.url = url
        self.step = 0

    def debug(self, msg):
        regex = ('.*\[download\] *([0-9.]*)% of *[0-9.]*.i_b '
                 'at *[0-9.]*.i_b/s ETA ([0-9:]*)')
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
        self.title = get_title(url)

    def debug(self, msg):
        regex = "\[download\] Downloading video (\d*) of (\d*)"
        match = re.match(regex, msg)
        if match is not None:
            current = float(match.groups()[0])
            total = float(match.groups()[1])
            percent = int(current*100/total)
            self.print_infos(f'Adding {self.title} ({percent}%%)')

        else:
            regex = "\[youtube:playlist\] [^:]*: Downloading page #(\d*)"
            match = re.match(regex, msg)
            if match is not None:
                page = match.groups()[0]
                self.print_infos(
                    f'Adding {self.title}: downloading page #{page}...')

    def warning(self, msg):
        self.print_infos('[YTDL warning] %s' % msg)

    def error(self, msg):
        self.print_infos('[YTDL error] %s' % msg)


class SearchLogger(object):
    def __init__(self, print_infos, search):
        self.print_infos = print_infos
        self.search = search

    def debug(self, msg):
        pass


class MediumDataLogger(object):
    def __init__(self, print_infos, title):
        self.print_infos = print_infos
        self.title = title

    def debug(self, msg):
        pass

    def warning(self, msg):
        self.print_infos('[YTDL warning] %s' % msg)

    def error(self, msg):
        self.print_infos('[YTDL error] %s' % msg)


def get_user_config():
    config = {}
    ytopts = Config.get('youtube')
    if ytopts['ip_version']:
        config['source_address'] = (
            '::' if ytopts['ip_version'] == 6 else '0.0.0.0')

    if ytopts['format']:
        config['format'] = ytopts['format']

    return config


def get_mpv_config():
    ytconfig = get_user_config()

    config = {}
    if 'format' in ytconfig:
        config['ytdl_format'] = ytconfig['format']
        del ytconfig['format']

    options = [f'{k.replace("_", "-")}={v}' for k, v in ytconfig.items()]
    config['ytdl_raw_options'] = ','.join(options)
    return config


def download(url, filename, print_infos):
    ydl_opts = {'logger': DownloadLogger(print_infos, url),
                'outtmpl': filename, 'format': 'mp4'}
    ydl_opts.update(get_user_config())
    with ytdl.YoutubeDL(ydl_opts) as ydl:
        try:
            ydl.download([url])
        except ytdl.DownloadError:
            raise DownloadError


def get_filename_extension(medium):
    return 'mp4'


def get_title(url):
    ydl_opts = {'quiet': True, 'no_warnings': True, 'ignoreerrors': True}
    ydl_opts.update(get_user_config())
    with ytdl.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False, process=False)
        if 'entries' not in info and 'url' in info:
            info = ydl.extract_info(info['url'], download=False,
                                    process=False)
    title = info['title']
    return re.sub(r'^Uploads from ', '', title)


def get_feed_url(url):
    feed_url = re.sub("/featured$|/videos$|/$", "", url)
    feed_url = feed_url.replace('/channel/',
                                '/feeds/videos.xml?channel_id=')
    feed_url = feed_url.replace('/user/', '/feeds/videos.xml?user=')
    feed_url = feed_url.replace('/playlist?list=',
                                '/feeds/videos.xml?playlist_id=')
    return feed_url


def get_data(source, opts, print_infos, force_all=False):
    new = 'update' not in opts or not opts['update']
    allow_video = 'type' in opts and opts['type'] in ('video', 'all')
    allow_channel = 'type' not in opts or opts['type'] in ('channel', 'all')

    mask = False
    if 'mask' in opts and opts['mask']:
        mask = opts['mask']

    if new:
        url = source
        start_date = 0
        method = 'ytdl'
    else:
        channel = source
        url = channel['url']
        # NOTE: cannot use daterange from ytdl, it won't change extract_info
        # (only for downloading)
        start_date = channel['updated']

        if force_all:
            method = 'ytdl'
            opts['count'] = 0
        else:
            method = opts['update_method']
            opts['count'] = -1

    if method == 'ytdl':
        title = None
        ydl_opts = {'logger': DataLogger(print_infos, url),
                    'ignoreerrors': True}
        ydl_opts.update(get_user_config())

        data = {}
        data['updated'] = int(time())
        data['type'] = 'youtube'

        data['items'] = []
        with ytdl.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False, process=False)

            # If it is a video
            if info['extractor'] == 'youtube':
                if not allow_video:
                    raise ValueError(f'{url} is a video, not a channel')
                channel_data = {}
                channel_data['title'] = info['uploader']
                channel_data['url'] = info['uploader_url']
                channel_data['updated'] = 0
                channel_data['items'] = []
                channel_data['type'] = 'youtube'

                medium = medium_from_ytdl(info)
                channel_data['items'].append(medium)

                return channel_data

            elif not allow_channel:
                raise ValueError(f'{url} is a channel not a video')

            # If not a playlist no info
            if info['_type'] == 'url':
                data['url'] = info['url']
                info = ydl.extract_info(info['url'], download=False,
                                        process=False)
            elif info['_type'] != 'playlist':
                print_infos("Cannot get data from %s" % url)
                return None

            if info is None or info['entries'] is None:
                print_infos("Cannot get data from %s" % url)
                return None
            title = info['title']

            if title is None:
                return None
            title = re.sub(r'Uploads from ', '', title)
            data['title'] = title
            data['url'] = info['webpage_url']

            work = []
            c = 0
            i = 0
            entries = []
            for entry in info['entries']:
                if 'strict' in opts and opts['strict'] and c == opts['count']:
                    break

                # Start from 'fromidx' element
                if 'fromidx' in opts and i < opts['fromidx']:
                    i += 1
                    continue

                if mask:
                    regex = re.compile(mask)
                    if not regex.match(entry['title']):
                        i += 1
                        continue

                if c != opts['count']:
                    work.append((c, entry))
                    entries.append(entry)
                    c += 1

                else:
                    entry['upload_date'] = '19700102'
                    entry['duration'] = 0
                    entry['description'] = ''
                    entry['thumbnail'] = ''
                    entry['valid'] = True
                    entries.append(entry)

                i += 1

            # Define task for getting info
            def extract_info_task(work, size):
                while True:
                    try:
                        c, entry = work.pop()
                    except IndexError:
                        break

                    if opts['count'] == -1:
                        print_infos(
                            f'Adding {title}: getting video info #{size-c}...')
                    else:
                        print_infos(
                            f'Adding {title}: getting info for {opts["count"]}'
                            f' videos ({int(c/opts["count"]*100)}%)...')
                    vidinfo = ydl.extract_info(entry['url'], download=False,
                                               process=False)
                    if vidinfo is None:
                        entry['upload_date'] = '19700102'
                        entry['duration'] = 0
                        entry['description'] = ''
                        entry['thumbnail'] = ''
                        entry['valid'] = True

                    else:
                        entry['upload_date'] = vidinfo['upload_date']
                        entry['duration'] = vidinfo['duration']
                        entry['description'] = vidinfo['description']
                        entry['thumbnail'] = vidinfo['thumbnail']
                        entry['valid'] = True

                    # If update, check not before last update
                    if start_date:
                        entry_timestamp = int(mktime(datetime.strptime(
                            entry['upload_date'], "%Y%m%d").timetuple()))
                        if entry_timestamp < start_date and not force_all:
                            break

            # Run threads to get info
            nthreads = 8
            threads = []
            args = (work, len(work))
            for t in range(nthreads):
                thread = Thread(target=extract_info_task, args=args)
                thread.daemon = True
                thread.start()
                threads.append(thread)

            for thread in threads:
                thread.join()

        # Merge valid info
        for entry in entries:
            if 'valid' in entry:
                medium = medium_from_ytdl(entry)
                medium['channel'] = title
                data['items'].append(medium)

        if opts['count'] == len(data['items']):
            data['addcount'] = opts['count']
        else:
            data['addcount'] = -1

    else:
        feed_url = get_feed_url(url)
        rss = fp.parse(feed_url)
        feed = rss.feed
        if not feed:
            print_infos(f'Cannot load {feed_url}')
            return None

        data = {}
        data['url'] = url
        data['title'] = printable_str(feed['title'])
        data['type'] = 'youtube'

        updated = 0
        data['items'] = []
        entries = rss.entries
        overlap = False
        for entry in entries:
            medium = {}
            medium['channel'] = data['title']
            medium['url'] = url
            medium['title'] = printable_str(entry['title'])
            medium['date'] = int(mktime(entry['published_parsed']))
            medium['description'] = entry['description']
            medium['link'] = expand_link(entry['yt_videoid'])

            updated = max(updated, medium['date'])

            # If too old, break
            if medium['date'] < start_date:
                overlap = True
                break

            if mask:
                regex = re.compile(mask)
                if not regex.match(medium['title']):
                    continue

            # Get missing info
            update_medium(medium, print_infos)

            data['items'].append(medium)

        # If last item is too recent compared to last update, we need ytdl
        if not overlap:
            opts['fromidx'] = len(entries)
            opts['update_method'] = 'ytdl'
            ytdl_data = get_new_data(channel, opts, print_infos)
            data['items'].extend(ytdl_data['items'])

        # Published parsed is the date of creation of the channel, so we take
        # the one from entries
        data['updated'] = updated

    return data


def get_all_data(url, opts, print_infos):
    return get_data(url, opts, print_infos)


def get_new_data(channel, opts, print_infos, force_all=False):
    opts['update'] = True
    if 'update_method' not in opts:
        opts['update_method'] = 'rss'
    return get_data(channel, opts, print_infos, force_all)


def get_video_data_only(url, opts, print_infos):
    opts['type'] = 'video'
    data = get_data(url, opts, print_infos)
    return data


def medium_from_ytdl(data):
    medium = {
        'title': printable_str(data['title']),
        'date': int(mktime(datetime.strptime(
            data['upload_date'], "%Y%m%d").timetuple())),
        'description': data['description'],
        'type': 'youtube',
        'duration': data['duration'],
    }

    try:
        medium['thumbnail'] = data['thumbnail']
    except KeyError:
        try:
            medium['thumbnail'] = data['thumbnails'][-1]['url']
        except:
            medium['thumbnail'] = ''

    if 'url' in data:
        medium['link'] = expand_link(data['url'])
    elif 'webpage_url' in data:
        medium['link'] = data['webpage_url']

    medium['channel'] = {}
    medium['channel']['title'] = data.get('uploader', '')
    medium['channel']['url'] = data.get('uploader_url', '')

    return medium


def get_medium_data(url, title, print_infos):
    ydl_opts = {'logger': MediumDataLogger(print_infos, title),
                'ignoreerrors': True}
    ydl_opts.update(get_user_config())
    with ytdl.YoutubeDL(ydl_opts) as ydl:
        data = ydl.extract_info(url, download=False, process=False)
    return data


def update_medium(medium, print_infos):
    data = get_medium_data(medium['link'], medium['title'], print_infos)
    if data is None:
        return False

    new_medium = medium_from_ytdl(data)
    medium.update(new_medium)
    return True


def get_clean_url(url):
    # Rename playlists with video link
    url = re.sub(r'watch\?v=.*&list=', 'playlist?list=', url)

    ydl_opts = {'quiet': True, 'no_warnings': True, 'ignoreerrors': True}
    ydl_opts.update(get_user_config())
    with ytdl.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False, process=False)

        try:
            if info['_type'] == 'url':
                return info['url']
            elif info['_type'] == 'playlist':
                return info['webpage_url']
            else:
                raise ValueError(f'Bad URL {url}')

        except KeyError:
            raise ValueError(f'Bad URL {url}')


def expand_link(link):
    if 'youtube' not in link:
        return 'https://www.youtube.com/watch?v='+link
    else:
        return link


def shrink_link(link):
    return re.sub(r'^https://www.youtube.com/watch\?v=', '', link)


def search_media(search, print_infos, get_info=False, count=30):
    ydl_opts = {'logger': SearchLogger(print_infos, 'search: {search}'),
                'ignoreerrors': True}
    ydl_opts.update(get_user_config())

    search_count = count if count > 0 else 'all'

    media = []
    with ytdl.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(f'ytsearch{search_count}:{search}',
                                download=False, process=False)

        for entry in info['entries']:
            if get_info:
                entry = ydl.extract_info(entry['url'], download=False,
                                         process=False)
                if entry is None:
                    continue
            else:
                entry['upload_date'] = '19700102'
                entry['duration'] = 0
                entry['uploader'] = ''
                entry['uploader_url'] = ''
                entry['description'] = ''
                entry['thumbnail'] = ''

            try:
                medium = medium_from_ytdl(entry)
                media.append(medium)
            except KeyError:
                pass

    return media
