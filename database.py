import sqlite3
from multiprocessing import Lock

from utils import *

class DataBase:
    def __init__(self, name, printInfos=print):
        self.mutex = Lock()
        self.printInfos = printInfos
        self.version = 1

        self.conn = sqlite3.connect(name, check_same_thread=False)
        self.cursor = self.conn.cursor()

        self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = list(map(lambda x: x[0], self.cursor.fetchall()))

        if not len(tables):
            self.cursor.executescript("""
                CREATE TABLE channels (
                    url TEXT PRIMARY KEY,
                    title TEXT,
                    type TEXT,
                    genre TEXT,
                    auto INTEGER,
                    last_update INTEGER
                );
            """)
            self.cursor.executescript("""
                CREATE TABLE media (
                    channel_url TEXT,
                    title TEXT,
                    date INTEGER,
                    duration INTEGER,
                    url TEXT,
                    location TEXT,
                    state INTEGER,
                    filename TEXT,
                    tags TEXT,
                    PRIMARY KEY (channel_url, title, date)
                );
            """)
            self.setUserVersion(self.version)

        else:
            dbVersion = self.getUserVersion()
            if self.version != dbVersion:
                self.printInfos(('Database is version "%d" but "%d" '
                    'needed: please update') % (dbVersion, self.version))
                exit(1)

        self.conn.commit()

    def getUserVersion(self):
        self.cursor.execute('PRAGMA user_version')
        return self.cursor.fetchone()[0]

    def setUserVersion(self, version):
        self.cursor.execute('PRAGMA user_version={:d}'.format(version))


    def selectMedia(self):
        self.cursor.execute("""SELECT * FROM media
                ORDER BY date DESC""")
        rows = self.cursor.fetchall()
        return list(map(self.listToMedium, rows))

    def listToMedium(self, mediumList):
        url = mediumList[0]
        channel = self.getChannel(url)['title']
        data = {}
        data['channel'] = channel
        data['url'] = url
        data['title'] = str(mediumList[1]) # str if title is only a number
        data['date'] = mediumList[2]
        data['duration'] = mediumList[3]
        data['link'] = mediumList[4]
        data['location'] = mediumList[5]
        data['state'] = mediumList[6]
        data['filename'] = mediumList[7]
        data['tags'] = mediumList[8]
        return data

    def mediumToList(self, medium):
        return (medium['url'], medium['title'], medium['date'], medium['duration'],
                medium['link'], medium['location'], medium['state'],
                medium['filename'], medium['tags'])

    def getChannel(self, url):
        """ Get Channel by url (primary key) """
        self.cursor.execute("SELECT * FROM channels WHERE url=?", (url,))
        rows = self.cursor.fetchall()
        if 1 != len(rows):
            return None
        return self.listToChannel(rows[0])

    def selectChannels(self):
        # TODO add filters: genre, auto
        self.cursor.execute("""SELECT * FROM channels
                ORDER BY last_update DESC""")
        rows = self.cursor.fetchall()
        return list(map(self.listToChannel, rows))

    def listToChannel(self, channelList):
        data = {}
        data['url'] = channelList[0]
        data['title'] = channelList[1]
        data['type'] = channelList[2]
        data['genre'] = channelList[3]
        data['auto'] = channelList[4]
        data['updated'] = channelList[5]
        return data

    def channelToList(self, channel):
        return (channel['url'], channel['title'], channel['type'],
                channel['genre'], channel['auto'], channel['updated'])

    def addChannel(self, data):
        channel = self.channelToList(data)
        params = ','.join('?'*len(channel))
        with self.mutex:
            self.cursor.execute('INSERT INTO channels VALUES (%s)' % params,
                     channel)
            self.conn.commit()

    def addMedia(self, data):
        updated = False
        url = data['url']

        channel = self.getChannel(url)
        if None == channel:
            return None

        # Find out if feed has updates
        updatedDate = channel['updated']
        feedDate = data['updated']
        newMedia = []
        newEntries = []
        if (feedDate > updatedDate): # new items
            # Filter feed to keep only new items
            for medium in data['items']:
                if medium['date'] > updatedDate:
                    if not 'duration' in medium: medium['duration'] = 0
                    if not 'location' in medium: medium['location'] = 'remote'
                    if not 'state' in medium: medium['state'] = 'unread'
                    if not 'filename' in medium: medium['filename'] = ''
                    if not 'tags' in medium: medium['tags'] = ''
                    newEntries.append(self.mediumToList(medium))
                    newMedia.append(medium)

            # Add new items to database
            if len(newEntries):
                try:
                    with self.mutex:
                        params = ','.join('?'*len(newEntries[0]))
                        self.cursor.executemany(
                            'INSERT INTO media VALUES (%s)' % params,
                            newEntries)
                        self.conn.commit()
                except sqlite3.IntegrityError:
                    self.printInfos('Cannot add %s' % str(newMedia))

        if len(newMedia):
            channel['url'] = url
            channel['updated'] = feedDate
            self.updateChannel(channel)

        return newMedia

    def updateChannel(self, channel):
        sql = """UPDATE channels
                    SET title = ?,
                        type = ?,
                        genre = ?,
                        auto = ?,
                        last_update = ?
                    WHERE url = ?"""
        args = (
                channel['title'],
                channel['type'],
                channel['genre'],
                channel['auto'],
                channel['updated'],
                channel['url'],
        )
        with self.mutex:
            self.cursor.execute(sql, args)
            self.conn.commit()

    def updateMedium(self, medium):
        sql = """UPDATE media
                    SET duration = ?,
                        url = ?,
                        location = ?,
                        state = ?,
                        filename = ?,
                        tags = ?
                    WHERE channel_url = ? and
                          title = ? and
                          date = ?"""
        if not 'duration' in medium: medium['duration'] = 0
        if not 'location' in medium: medium['location'] = 'remote'
        if not 'state' in medium: medium['state'] = 'unread'
        if not 'filename' in medium: medium['filename'] = ''
        if not 'tags' in medium: medium['tags'] = ''
        args = (
                medium['duration'], medium['link'], medium['location'],
                medium['state'], medium['filename'], medium['tags'],
                medium['url'], medium['title'], medium['date']
        )
        with self.mutex:
            self.cursor.execute(sql, args)
            self.conn.commit()
