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
from multiprocessing import Lock


class DataBase:
    def __init__(self, name, print_infos=print):
        self.mutex = Lock()
        self.print_infos = print_infos
        self.version = 2
        # channels by url, useful to get the same object in media
        self.channels = {}

        self.conn = sqlite3.connect(name, check_same_thread=False)
        self.cursor = self.conn.cursor()

        self.cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")
        tables = list(map(lambda x: x[0], self.cursor.fetchall()))

        if not tables:
            self.cursor.executescript("""
                CREATE TABLE channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL UNIQUE,
                    title TEXT,
                    type TEXT,
                    genre TEXT,
                    auto INTEGER,
                    last_update INTEGER,
                    disabled INTEGER
                );
                CREATE INDEX url ON channels (url);
            """)
            self.cursor.executescript("""
                CREATE TABLE media (
                    cid TEXT,
                    title TEXT,
                    date INTEGER,
                    duration INTEGER,
                    url TEXT,
                    location TEXT,
                    state TEXT,
                    filename TEXT,
                    tags TEXT,
                    description TEXT,
                    PRIMARY KEY (cid, title, date)
                );
            """)
            self.set_user_version(self.version)

        else:
            db_version = self.get_user_version()
            if self.version != db_version:
                self.print_infos(('Database is version "%d" but "%d" needed: '
                                 'please update') % (db_version, self.version))
                exit(1)

        self.conn.commit()

    def get_user_version(self):
        self.cursor.execute('PRAGMA user_version')
        return self.cursor.fetchone()[0]

    def set_user_version(self, version):
        self.cursor.execute('PRAGMA user_version={:d}'.format(version))

    def select_media(self):
        self.cursor.execute("""SELECT * FROM media
                ORDER BY date DESC""")
        rows = self.cursor.fetchall()
        return list(map(self.list_to_medium, rows))

    def list_to_medium(self, medium_list):
        channel_id = medium_list[0]
        channel = self.get_channel(channel_id)
        data = {}
        data['channel'] = channel
        data['cid'] = channel_id
        data['title'] = str(medium_list[1])  # str if title is only a number
        data['date'] = medium_list[2]
        data['duration'] = medium_list[3]
        data['link'] = medium_list[4]
        data['location'] = medium_list[5]
        data['state'] = medium_list[6]
        data['filename'] = medium_list[7]
        data['tags'] = medium_list[8]
        data['description'] = medium_list[9]
        return data

    def medium_to_list(self, medium):
        return (medium['cid'], medium['title'], medium['date'],
                medium['duration'], medium['link'], medium['location'],
                medium['state'], medium['filename'], medium['tags'],
                medium['description'])

    def get_channel(self, channel_id):
        try:
            return self.channels[channel_id]
        except KeyError:
            """ Get Channel by id (primary key) """
            self.cursor.execute("SELECT * FROM channels WHERE id=?",
                                (channel_id,))
            rows = self.cursor.fetchall()
            if 1 != len(rows):
                return None
            return self.list_to_channel(rows[0])

    # TODO XXX use when checking exists
    def find_channel(self, url):
        """ Get Channel by url """
        self.cursor.execute("SELECT * FROM channels WHERE url=?", (url,))
        rows = self.cursor.fetchall()
        if 1 != len(rows):
            return None
        return self.list_to_channel(rows[0])

    def select_channels(self):
        # if already called
        if self.channels:
            return list(self.channels.values())
        else:
            self.cursor.execute("""SELECT * FROM channels
                    ORDER BY last_update DESC""")
            rows = self.cursor.fetchall()
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
        data['disabled'] = int(channel_list[7]) == 1

        # Save it in self.channels
        if not data['id'] in self.channels:
            self.channels[data['id']] = data
        else:
            self.channels[data['id']].update(data)

        return data

    def channel_to_list(self, channel):
        return (channel['url'], channel['title'],
                channel['type'], channel['genre'], channel['auto'],
                channel['updated'], int(channel['disabled']))

    def add_channel(self, data):
        channel = self.channel_to_list(data)
        params = ','.join('?'*len(channel))
        with self.mutex:
            self.cursor.execute('INSERT INTO channels (url, title, type, '
                                'genre, auto, last_update, disabled) '
                                'VALUES (%s)' %
                                params, channel)
            self.conn.commit()

        cid = self.cursor.lastrowid
        data['id'] = cid
        # Save it in self.channels
        if cid not in self.channels:
            self.channels[cid] = data
        else:
            self.channels[cid].update(data)

    def add_media(self, data, update=False):
        cid = data['id']

        channel = self.get_channel(cid)
        if channel is None:
            return None

        # Find out if feed has updates
        if update:
            updated_date = 0
        else:
            updated_date = channel['updated']
        feed_date = data['updated']
        new_media = []
        new_entries = []
        if (feed_date > updated_date):  # new items
            # Filter feed to keep only new items
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
                    new_entries.append(self.medium_to_list(medium))
                    new_media.append(medium)

            # Add new items to database
            if new_entries:
                try:
                    with self.mutex:
                        params = ','.join('?'*len(new_entries[0]))
                        self.cursor.executemany(
                            'INSERT INTO media VALUES (%s)' % params,
                            new_entries)
                        self.conn.commit()
                except sqlite3.IntegrityError:
                    self.print_infos('Cannot add %s' % str(new_media))

        if new_media:
            channel['id'] = cid
            channel['updated'] = feed_date
            self.update_channel(channel)

        return new_media

    def update_channel(self, channel):
        sql = """UPDATE channels
                    SET title = ?,
                        type = ?,
                        genre = ?,
                        auto = ?,
                        last_update = ?,
                        disabled = ?
                    WHERE id = ?"""
        args = (
                channel['title'],
                channel['type'],
                channel['genre'],
                channel['auto'],
                channel['updated'],
                channel['disabled'],
                channel['id'],
        )
        with self.mutex:
            self.cursor.execute(sql, args)
            self.conn.commit()

    def update_medium(self, medium):
        sql = """UPDATE media
                    SET duration = ?,
                        url = ?,
                        location = ?,
                        state = ?,
                        filename = ?,
                        tags = ?
                    WHERE cid = ? and
                          title = ? and
                          date = ?"""
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
                medium['duration'], medium['link'], medium['location'],
                medium['state'], medium['filename'], medium['tags'],
                medium['cid'], medium['title'], medium['date']
        )
        with self.mutex:
            self.cursor.execute(sql, args)
            self.conn.commit()

    def channel_get_unread_media(self, cid):
        self.cursor.execute(
            "SELECT * FROM media WHERE cid=? AND state='unread'",
            (cid, ))
        rows = self.cursor.fetchall()
        return list(map(self.list_to_medium, rows))

    def channel_get_all_media(self, cid):
        self.cursor.execute("SELECT * FROM media WHERE cid=?", (cid,))
        rows = self.cursor.fetchall()
        return list(map(self.list_to_medium, rows))

    def channel_remove(self, cids):
        for cid in cids:
            channel = self.get_channel(cid)
            if channel is None:
                continue
            # Remove channels
            sql = "DELETE FROM channels where id = ?"
            self.cursor.execute(sql, [cid])

            # Remove media
            sql = "DELETE FROM media where cid = ?"
            self.cursor.execute(sql, [cid])
            self.conn.commit()
