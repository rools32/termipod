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

def get_header(media, name):
    return (
        '#EXTM3U\n'
        '#PLAYLIST:'+name+'\n'
    )


def medium_to_entry(i, m):
    file = m['filename']
    link = m['link']
    title = m['title']
    artist = m['channel']['title'].replace(' - ', ' -- ')
    clink = m['channel']['url']
    duration = m['duration']
    thumbnail = m['thumbnail']
    date = m['date']

    entry = (
        f'#EXTINF:{duration}, {artist} - {title}\n'
        f'#EXTIMG:{thumbnail}\n'
        f'#TERMIPOD-CLINK:{clink}\n'
        f'#TERMIPOD-DATE:{date}\n'
    )
    if file:
        entry += (f'#TERMIPOD-LINK:{link}\n'
                  f'{file}\n')
    else:
        entry += link+'\n'

    return entry


def get_extension():
    return '.m3u'


def from_media(media, name, print_infos):
    playlist = [get_header(media, name)]

    for i, m in enumerate(media):
        playlist.append(medium_to_entry(i, m))

    destfile = name+get_extension()
    try:
        with open(destfile, 'w') as f:
            data = '\n'.join(playlist)
            f.write(data)
    except FileNotFoundError as e:
        print_infos(e, mode='error')


def to_media(name):
    srcfile = name+get_extension()

    media = []
    with open(srcfile) as f:
        medium = {}
        medium['channel'] = {}
        for line in f:
            line = line.strip()
            # Emtpy line
            if not line:
                continue

            # m3u directive
            elif line.startswith('#EXT'):
                line = line[4:]
                if line.startswith('INF:'):
                    line = line[4:]
                    duration, info = line.split(',', 1)
                    artist, title = info.split(' - ', 1)
                    medium['duration'] = int(duration)
                    medium['channel']['title'] = artist
                    medium['title'] = title
                elif line.startswith('IMG'):
                    line = line[4:]
                    medium['thumbnail'] = line

            # termipod directive
            elif line.startswith('#TERMIPOD-'):
                line = line[len('#TERMIPOD-'):]
                if line.startswith('LINK:'):
                    line = line[len('LINK:'):]
                    medium['link'] = line
                elif line.startswith('CLINK:'):
                    line = line[len('CLINK:'):]
                    medium['channel']['url'] = line
                elif line.startswith('DATE:'):
                    line = line[len('DATE:'):]
                    medium['date'] = int(line)

            # Comments
            elif line.startswith('#'):
                continue

            # URL
            else:
                if 'link' not in medium or medium['link'] == line:
                    medium['filename'] = ''
                    medium['link'] = line
                else:
                    medium['filename'] = line
                media.append(medium)
                medium = {}
                medium['channel'] = {}

    return media
