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

import sqlite3
import sys
from multiprocessing import Lock


class DataBase:
    def __init__(self, name, print_infos=print):
        self.mutex = Lock()
        self.print_infos = print_infos
        self.version = 6
        # channels by url, useful to get the same object in media
        self.channels = {}

        self.conn = sqlite3.connect(name, check_same_thread=False)

        cursor = self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")
        tables = list(map(lambda x: x[0], cursor.fetchall()))

        if not tables:
            with self.conn:
                self.conn.executescript("""
                    CREATE TABLE channels (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        url TEXT NOT NULL,
                        title TEXT,
                        type TEXT,
                        genre TEXT,
                        auto INTEGER,
                        last_update INTEGER,
                        addcount INTEGER,
                        disabled INTEGER,
                        mask TEXT
                    );
                """)
                self.conn.executescript("""
                    CREATE TABLE media (
                        url TEXT,
                        cid INTEGER,
                        title TEXT,
                        date INTEGER,
                        duration INTEGER,
                        location TEXT,
                        state TEXT,
                        filename TEXT,
                        tags TEXT,
                        description TEXT,
                        PRIMARY KEY (url, cid)
                    );
                """)
                self.set_user_version(self.version)

        else:
            if self.version != self.get_user_version():
                # Update db from 3 to 4
                if 3 == self.get_user_version():
                    # Change primary key of media table
                    with self.conn:
                        self.conn.executescript("""
                            CREATE TABLE media_tmp (
                                url TEXT,
                                cid INTEGER,
                                title TEXT,
                                date INTEGER,
                                duration INTEGER,
                                location TEXT,
                                state TEXT,
                                filename TEXT,
                                tags TEXT,
                                description TEXT,
                                PRIMARY KEY (url, cid)
                            );
                        """)
                        self.conn.executescript("""
                            INSERT INTO media_tmp
                                (url, cid, title, date, duration, location,
                                 state, filename, tags, description)
                                SELECT url, cid, title, date, duration,
                                       location, state, filename, tags,
                                       description
                                       FROM media;
                        """)
                        self.conn.executescript("""
                            DROP TABLE media;
                        """)
                        self.conn.executescript("""
                            ALTER TABLE media_tmp RENAME TO media;
                        """)
                        self.set_user_version(4)

                if 4 == self.get_user_version():
                    with self.conn:
                        self.conn.execute(
                            "ALTER TABLE channels ADD COLUMN 'mask' 'TEXT'")
                        self.set_user_version(5)

                if 5 == self.get_user_version():
                    self.conn.execute(
                        "DROP INDEX url;")
                    # Remove unique constraint from channels table
                    with self.conn:
                        self.conn.executescript("""
                            CREATE TABLE channels_tmp (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                url TEXT NOT NULL,
                                title TEXT,
                                type TEXT,
                                genre TEXT,
                                auto INTEGER,
                                last_update INTEGER,
                                addcount INTEGER,
                                disabled INTEGER,
                                mask TEXT
                            );
                        """)
                        self.conn.executescript("""
                            INSERT INTO channels_tmp
                                (id, url, title, type, genre, auto,
                                last_update, addcount, disabled, mask)
                                SELECT id, url, title, type, genre, auto,
                                       last_update, addcount, disabled, mask
                                       FROM channels;
                        """)
                        self.conn.executescript("""
                            DROP TABLE channels;
                        """)
                        self.conn.executescript("""
                            ALTER TABLE channels_tmp RENAME TO channels;
                        """)
                        self.set_user_version(6)

                if self.version != self.get_user_version():
                    self.print_infos(
                        'Database is version "%d" but "%d" needed: '
                        'please update' %
                        (self.get_user_version(), self.version))
                    exit(1)

    def get_user_version(self):
        cursor = self.conn.execute('PRAGMA user_version')
        return cursor.fetchone()[0]

    def set_user_version(self, version):
        self.conn.execute('PRAGMA user_version={:d}'.format(version))

    def select_media(self):
        cursor = self.conn.execute("""SELECT * FROM media
                ORDER BY date DESC""")
        rows = cursor.fetchall()
        return list(map(self.list_to_medium, rows))

    def list_to_medium(self, medium_list):
        data = {}
        data['link'] = medium_list[0]
        channel_id = medium_list[1]
        data['title'] = str(medium_list[2])  # str if title is only a number
        data['date'] = medium_list[3]
        data['duration'] = medium_list[4]
        data['location'] = medium_list[5]
        data['state'] = medium_list[6]
        data['filename'] = medium_list[7]
        data['tags'] = medium_list[8]
        data['description'] = medium_list[9]

        data['cid'] = channel_id
        channel = self.get_channel(channel_id)
        data['channel'] = channel

        # Build complete yt link
        if channel['type'] == 'youtube':  # TODO move into backends/yt
            data['id'] = data['link']
            if 'youtube' not in data['link']:
                data['link'] = 'https://www.youtube.com/watch?v='+data['link']

        return data

    def medium_to_list(self, medium):
        return (medium['link'], medium['cid'], medium['title'], medium['date'],
                medium['duration'], medium['location'], medium['state'],
                medium['filename'], medium['tags'], medium['description'])

    def get_channel(self, channel_id):
        try:
            return self.channels[channel_id]
        except KeyError:
            """ Get Channel by id (primary key) """
            cursor = self.conn.execute("SELECT * FROM channels WHERE id=?",
                                       (channel_id,))
            rows = cursor.fetchall()
            if 1 != len(rows):
                return None
            return self.list_to_channel(rows[0])

    def find_channels(self, url):
        """ Get Channel by url """
        cursor = self.conn.execute(
            "SELECT * FROM channels WHERE url=?", (url,))
        rows = cursor.fetchall()
        return [self.list_to_channel(row) for row in rows]

    def select_channels(self):
        # if already called
        if self.channels:
            return list(self.channels.values())
        else:
            cursor = self.conn.execute("""SELECT * FROM channels
                    ORDER BY last_update DESC""")
            rows = cursor.fetchall()
            return list(map(self.list_to_channel, rows))

    def list_to_channel(self, channel_list):
        data = {}
        data['id'] = channel_list[0]
        data['url'] = channel_list[1]
        data['title'] = channel_list[2]
        data['type'] = channel_list[3]
        data['genre'] = channel_list[4]
        data['auto'] = channel_list[5]
        data['updated'] = channel_list[6]
        data['addcount'] = int(channel_list[7])
        data['disabled'] = int(channel_list[8]) == 1
        data['mask'] = channel_list[9]

        # Save it in self.channels
        if not data['id'] in self.channels:
            self.channels[data['id']] = data
        else:
            self.channels[data['id']].update(data)

        return data

    def channel_to_list(self, channel):
        return (channel['url'], channel['title'],
                channel['type'], channel['genre'], channel['auto'],
                channel['updated'], int(channel['addcount']),
                int(channel['disabled']), channel['mask'])

    def add_channel(self, data):
        channel = self.channel_to_list(data)
        params = ','.join('?'*len(channel))
        with self.mutex, self.conn:
            cursor = self.conn.execute(
                'INSERT INTO channels (url, title, type, '
                'genre, auto, last_update, addcount, disabled, mask) '
                'VALUES (%s)' % params, channel)
            cid = cursor.lastrowid

            data['id'] = cid
            # Save it in self.channels
            if cid not in self.channels:
                self.channels[cid] = data
            else:
                self.channels[cid].update(data)

            # Update medium list
            media = self.add_media(data, new=True, mutex=False)

        return media

    def add_media(self, data, new=False, mutex=True):
        cid = data['id']

        channel = self.get_channel(cid)
        if channel is None:
            return None

        # Find out if feed has updates
        if new:
            updated_date = -1
        else:
            updated_date = channel['updated']
        feed_date = data['updated']
        new_media = []
        new_entries = []
        if (feed_date > updated_date):  # new items
            # Filter feed to keep only new items
            media_by_key = {}
            for medium in data['items']:
                medium['cid'] = cid
                medium['channel'] = self.channels[cid]
                if medium['date'] > updated_date:
                    if 'duration' not in medium:
                        medium['duration'] = 0
                    if 'location' not in medium:
                        medium['location'] = 'remote'
                    if 'state' not in medium:
                        medium['state'] = 'unread'
                    if 'filename' not in medium:
                        medium['filename'] = ''
                    if 'tags' not in medium:
                        medium['tags'] = ''
                    new_entry = self.medium_to_list(medium)

                    # Check medium was not already in db
                    if new:
                        not_found = True
                    else:
                        cur = self.conn.execute(
                            "SELECT url FROM media WHERE url = ? and cid = ?",
                            (medium['link'], medium['cid'])
                        )
                        not_found = cur.fetchone() is None

                    if not_found:
                        # Remove duplicates from playlist
                        if (medium['link'], medium['cid']) in media_by_key:
                            continue

                        media_by_key[(medium['link'], medium['cid'])] = medium
                        new_entries.append(new_entry)
                        new_media.append(medium)

            # Add new items to database
            if new_entries:
                channel['id'] = cid
                channel['updated'] = feed_date
                try:
                    params = ','.join('?'*len(new_entries[0]))
                    sql = 'INSERT INTO media VALUES (%s)' % params
                    if mutex:
                        self.mutex.acquire()
                    with self.conn:
                        self.conn.executemany(sql, new_entries)
                        self.update_channel(channel, mutex=False)
                    if mutex:
                        self.mutex.release()
                except sqlite3.IntegrityError as e:
                    self.print_infos(
                        f'Cannot add media from {channel["title"]}: '+str(e))
                    return None

        return new_media

    def update_channel(self, channel, mutex=True):
        sql = """UPDATE channels
                    SET title = ?,
                        type = ?,
                        genre = ?,
                        auto = ?,
                        last_update = ?,
                        addcount = ?,
                        disabled = ?
                    WHERE id = ?"""
        args = (
                channel['title'],
                channel['type'],
                channel['genre'],
                channel['auto'],
                channel['updated'],
                channel['addcount'],
                channel['disabled'],
                channel['id'],
        )
        if mutex:
            with self.mutex, self.conn:
                self.conn.execute(sql, args)
        else:
            with self.conn:
                self.conn.execute(sql, args)

    def update_medium(self, medium):
        sql = """UPDATE media
                    SET duration = ?,
                        date = ?,
                        location = ?,
                        state = ?,
                        filename = ?,
                        tags = ?
                    WHERE url = ? and cid = ?"""
        if 'duration' not in medium:
            medium['duration'] = 0
        if 'location' not in medium:
            medium['location'] = 'remote'
        if 'state' not in medium:
            medium['state'] = 'unread'
        if 'filename' not in medium:
            medium['filename'] = ''
        if 'tags' not in medium:
            medium['tags'] = ''
        args = (
            medium['duration'], medium['date'], medium['location'],
            medium['state'], medium['filename'], medium['tags'],
            medium['id'], medium['cid']
        )
        with self.mutex, self.conn:
            ret = self.conn.execute(sql, args)

        return ret.rowcount == 1

    def channel_get_unread_media(self, cid):
        cursor = self.conn.execute(
            "SELECT * FROM media WHERE cid=? AND state='unread'",
            (cid, ))
        rows = cursor.fetchall()
        return list(map(self.list_to_medium, rows))

    def channel_get_all_media(self, cid):
        cursor = self.conn.execute("SELECT * FROM media WHERE cid=?", (cid,))
        rows = cursor.fetchall()
        return list(map(self.list_to_medium, rows))

    def channel_remove(self, cids):
        for cid in cids:
            channel = self.get_channel(cid)
            if channel is None:
                continue

            with self.conn:
                # Remove channels
                sql = "DELETE FROM channels where id = ?"
                self.conn.execute(sql, [cid])

                # Remove media
                sql = "DELETE FROM media where cid = ?"
                self.conn.execute(sql, [cid])
