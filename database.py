import sqlite3
from utils import *

class DataBase:
    def __init__(self, name):
        self.conn = sqlite3.connect(name)
        #conn = sqlite3.connect(':memory:')
        self.cursor = self.conn.cursor()

        self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = map(lambda x: x[0], self.cursor.fetchall())

        if not 'channels' in tables:
            self.cursor.executescript("""
                CREATE TABLE channels (
                    url str PRIMARY KEY,
                    title STR,
                    type STR,
                    genre STR,
                    auto INT,
                    last_update INT
                );
            """)
        if not 'videos' in tables:
            self.cursor.executescript("""
                CREATE TABLE videos (
                    channel_url str,
                    title str,
                    date int,
                    duration int,
                    url str,
                    status int,
                    filename str,
                    tags str,
                    PRIMARY KEY (channel_url, title, date)
                );
            """)
        self.conn.commit()

    def selectVideos(self):
        self.cursor.execute("""SELECT * FROM videos
                ORDER BY date DESC""")
        rows = self.cursor.fetchall()
        return list(map(self.listToItem, rows))

    def listToItem(self, videoList):
        url = videoList[0]
        channel = self.getChannel(url)['title']
        data = {}
        data['channel'] = channel
        data['url'] = url
        data['title'] = str(videoList[1]) # str if title is only a number
        data['date'] = videoList[2]
        data['duration'] = videoList[3]
        data['link'] = videoList[4]
        data['status'] = videoList[5]
        data['filename'] = videoList[6]
        data['tags'] = videoList[7]
        return data

    def itemToList(self, item):
        return (item['url'], item['title'], item['date'], item['duration'],
                item['link'], item['status'], item['filename'], item['tags'])

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

    def addChannel(self, url, title, feedtype, genre, auto, data):
        # use chennelDictoToList TODO
        channel = [ url, title, feedtype, genre, auto, 0]
        self.cursor.execute('INSERT INTO channels VALUES (?,?,?,?,?,?)',
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
        if (feedDate > updatedDate): # new items
            # Filter feed to keep only new items
            newVideos = [ self.itemToList(v)
                for v in data['items'] if v['date'] > updatedDate ]

            if len(newVideos):
                updated = True

            # Add new items to database
            try:
                self.cursor.executemany('INSERT INTO videos VALUES (?,?,?,?,?,?,?,?)',
                        newVideos)
            except sqlite3.IntegrityError:
                self.printInfos('Cannot add %s' % str(newVideos))
                print(1+str(2))

            self.conn.commit()

        if updated:
            channel['url'] = url
            channel['updated'] = feedDate
            self.updateChannel(url, channel)

        return updated

    def updateChannel(self, channel):
        sql = """UPDATE channels
                    SET title = ?,
                    SET type = ?,
                    SET genre = ?,
                    SET auto = ?,
                    SET last_update = ?,
                    WHERE url = ?"""
        args = (
                channel['title'],
                channel['type'],
                channel['genre'],
                channel['auto'],
                channel['updated'],
                channel['url'],
        )
        self.cursor.execute(sql, args)
        self.conn.commit()

    def updateVideo(self, video):
        sql = """UPDATE videos
                    SET duration = ?,
                        url = ?,
                        status = ?,
                        filename = ?,
                        tags = ?
                    WHERE channel_url = ? and
                          title = ? and
                          date = ?"""
        args = (
                video['duration'], video['link'], video['status'],
                video['filename'], video['tags'],
                video['url'], video['title'], video['date']
        )
        self.cursor.execute(sql, args)
        self.conn.commit()
