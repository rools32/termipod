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


def get_user_version(conn):
    cursor = conn.execute('PRAGMA user_version')
    return cursor.fetchone()[0]


def set_user_version(conn, version):
    conn.execute('PRAGMA user_version={:d}'.format(version))


def update_version(conn, version):
    if version != get_user_version(conn):
        # Update db from 3 to 4
        if 3 == get_user_version(conn):
            # Change primary key of media table
            with conn:
                conn.executescript("""
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
                conn.executescript("""
                    INSERT INTO media_tmp
                        (url, cid, title, date, duration, location,
                         state, filename, tags, description)
                        SELECT url, cid, title, date, duration,
                               location, state, filename, tags,
                               description
                               FROM media;
                """)
                conn.executescript("""
                    DROP TABLE media;
                """)
                conn.executescript("""
                    ALTER TABLE media_tmp RENAME TO media;
                """)
                set_user_version(conn, 4)

        if 4 == get_user_version(conn):
            with conn:
                conn.execute(
                    "ALTER TABLE channels ADD COLUMN 'mask' 'TEXT'")
                set_user_version(conn, 5)

        if 5 == get_user_version(conn):
            conn.execute(
                "DROP INDEX url;")
            # Remove unique constraint from channels table
            with conn:
                conn.executescript("""
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
                conn.executescript("""
                    INSERT INTO channels_tmp
                        (id, url, title, type, genre, auto,
                        last_update, addcount, disabled, mask)
                        SELECT id, url, title, type, genre, auto,
                               last_update, addcount, disabled, mask
                               FROM channels;
                """)
                conn.executescript("""
                    DROP TABLE channels;
                """)
                conn.executescript("""
                    ALTER TABLE channels_tmp RENAME TO channels;
                """)
                set_user_version(conn, 6)

        if 6 == get_user_version(conn):
            # Rename colomn genre to category
            with conn:
                conn.executescript("""
                    CREATE TABLE channels_tmp (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        url TEXT NOT NULL,
                        title TEXT,
                        type TEXT,
                        category TEXT,
                        auto INTEGER,
                        last_update INTEGER,
                        addcount INTEGER,
                        disabled INTEGER,
                        mask TEXT
                    );
                """)
                conn.executescript("""
                    INSERT INTO channels_tmp
                        (id, url, title, type, category, auto,
                        last_update, addcount, disabled, mask)
                        SELECT id, url, title, type, genre, auto,
                               last_update, addcount, disabled, mask
                               FROM channels;
                """)
                conn.executescript("""
                    DROP TABLE channels;
                """)
                conn.executescript("""
                    ALTER TABLE channels_tmp RENAME TO channels;
                """)
                set_user_version(conn, 7)

        if version != get_user_version(conn):
            print(version)
            print(get_user_version(conn))
            return False
        return True
