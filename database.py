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
                CREATE TABLE videos (
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


    def selectVideos(self):
        self.cursor.execute("""SELECT * FROM videos
                ORDER BY date DESC""")
        rows = self.cursor.fetchall()
        return list(map(self.listToVideo, rows))

    def listToVideo(self, videoList):
        url = videoList[0]
        channel = self.getChannel(url)['title']
        data = {}
        data['channel'] = channel
        data['url'] = url
        data['title'] = str(videoList[1]) # str if title is only a number
        data['date'] = videoList[2]
        data['duration'] = videoList[3]
        data['link'] = videoList[4]
        data['location'] = videoList[5]
        data['state'] = videoList[6]
        data['filename'] = videoList[7]
        data['tags'] = videoList[8]
        return data

    def videoToList(self, video):
        return (video['url'], video['title'], video['date'], video['duration'],
                video['link'], video['location'], video['state'],
                video['filename'], video['tags'])

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

    def addVideos(self, data):
        updated = False
        url = data['url']

        channel = self.getChannel(url)
        if None == channel:
            return None

        # Find out if feed has updates
        updatedDate = channel['updated']
        feedDate = data['updated']
        newVideos = []
        newEntries = []
        if (feedDate > updatedDate): # new items
            # Filter feed to keep only new items
            for video in data['items']:
                if video['date'] > updatedDate:
                    if not 'duration' in video: video['duration'] = 0
                    if not 'location' in video: video['location'] = 'remote'
                    if not 'state' in video: video['state'] = 'unread'
                    if not 'filename' in video: video['filename'] = ''
                    if not 'tags' in video: video['tags'] = ''
                    newEntries.append(self.videoToList(video))
                    newVideos.append(video)

            # Add new items to database
            if len(newEntries):
                try:
                    with self.mutex:
                        params = ','.join('?'*len(newEntries[0]))
                        self.cursor.executemany(
                            'INSERT INTO videos VALUES (%s)' % params,
                            newEntries)
                        self.conn.commit()
                except sqlite3.IntegrityError:
                    self.printInfos('Cannot add %s' % str(newVideos))

        if len(newVideos):
            channel['url'] = url
            channel['updated'] = feedDate
            self.updateChannel(channel)

        return newVideos

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

    def updateVideo(self, video):
        sql = """UPDATE videos
                    SET duration = ?,
                        url = ?,
                        location = ?,
                        state = ?,
                        filename = ?,
                        tags = ?
                    WHERE channel_url = ? and
                          title = ? and
                          date = ?"""
        if not 'duration' in video: video['duration'] = 0
        if not 'location' in video: video['location'] = 'remote'
        if not 'state' in video: video['state'] = 'unread'
        if not 'filename' in video: video['filename'] = ''
        if not 'tags' in video: video['tags'] = ''
        args = (
                video['duration'], video['link'], video['location'],
                video['state'], video['filename'], video['tags'],
                video['url'], video['title'], video['date']
        )
        with self.mutex:
            self.cursor.execute(sql, args)
            self.conn.commit()
