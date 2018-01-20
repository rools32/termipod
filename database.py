import sqlite3

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

    def selectVideos(self, what=None, value=None):
        self.cursor.execute("SELECT * FROM videos")
        # TODO
        #self.cursor.execute("SELECT * FROM tasks WHERE priority=?", (priority,))
        rows = self.cursor.fetchall()
        return list(map(self.videoListToDict, rows))

    def videoListToDict(self, videoList):
        url = videoList[0]
        channel = self.getChannel(url)['title']
        data = {}
        data['url'] = url
        data['channel'] = channel
        data['title'] = videoList[1]
        data['date'] = videoList[2]
        data['duration'] = videoList[3]
        data['link'] = videoList[4]
        data['status'] = videoList[5]
        data['filename'] = videoList[6]
        data['tag'] = videoList[7]
        return data

    def getChannel(self, url):
        """ Get Channel by url (primary key) """
        self.cursor.execute("SELECT * FROM channels WHERE url=?", (url,))
        rows = self.cursor.fetchall()
        if 1 != len(rows):
            return None
        return self.channelListToDict(rows[0])

    def selectChannels(self):
        # TODO add filters: genre, auto
        self.cursor.execute("SELECT * FROM channels")
        rows = self.cursor.fetchall()
        return list(map(self.channelListToDict, rows))

    def channelListToDict(self, channelList):
        data = {}
        data['url'] = channelList[0]
        data['title'] = channelList[1]
        data['type'] = channelList[2]
        data['genre'] = channelList[3]
        data['auto'] = channelList[4]
        data['updated'] = channelList[5]
        return data

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
            newVideos = [ (data['url'], v['title'], v['date'],
                v['duration'], v['link'], 'new', '', '')
                for v in data['items'] if v['date'] > updatedDate ]

            if len(newVideos):
                updated = True

            # Add new items to database
            self.cursor.executemany('INSERT INTO videos VALUES (?,?,?,?,?,?,?,?)',
                    newVideos)
            self.conn.commit()

        if updated:
            self.channelUpdate(url, feedDate)

        return updated

    def channelUpdate(self, url, date):
        self.cursor.execute("UPDATE channels SET last_update = ? WHERE url = ?",
                [date, url])
        self.conn.commit()

    def channelSetAuto(self, url, auto=True):
        pass

    def makrAsDownloaded(self, channel, title, date, filename):
        sql = """UPDATE videos
                    SET filename = ?,
                        status = 'downloaded'
                    WHERE channel_url = ? and
                          title = ? and
                          date = ?"""
        self.cursor.execute(sql, (filename, channel, title, date))
        self.conn.commit()
