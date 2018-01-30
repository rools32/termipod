import re

import backends
import player
from database import DataBase
from utils import *

class ItemList():
    def __init__(self, dbName, printInfos=print):
        self.dbName = dbName
        self.db = DataBase(dbName, printInfos)
        self.videos = self.db.selectVideos()
        self.channels = self.db.selectChannels()
        self.printInfos = printInfos
        self.videoAreas = []
        self.channelAreas = []
        self.player = player.Player(self, self.printInfos)
        self.downloadManager = backends.DownloadManager(self, self.printInfos)

    def updateChannels(self, channels=None):
        if None == channels:
            channels = self.db.selectVideos()
        self.channels.clear()
        self.channels.extend(channels)
        self.updateChannelAreas()

    def updateVideos(self, videos=None):
        if None == videos:
            videos = self.db.selectVideos()
        self.videos.clear()
        self.videos.extend(videos)
        self.updateVideoAreas()

    def updateVideoAreas(self):
        for area in self.videoAreas:
            area.resetContent()

    def updateChannelAreas(self):
        for area in self.channelAreas:
            area.resetContent()

    def add(self, video):
        self.videos.append(video)
        self.updateStrings()

    def download(self, indices):
        if int == type(indices):
            indices = [indices]

        for idx in indices:
            item = self.videos[idx]
            link = item['link']

            channel = self.db.getChannel(item['url'])
            self.downloadManager.add(item, channel)
        self.updateVideoAreas()

    def play(self, idx):
        item = self.videos[idx]
        self.player.play(item)

    def playadd(self, idx):
        item = self.videos[idx]
        self.player.add(item)

    def switchRead(self, indices):
        if int == type(indices):
            indices = [indices]

        for idx in indices:
            item = self.videos[idx]
            if 'read' == item['state']:
                item['state'] = 'unread'
            else:
                item['state'] = 'read'
            self.db.updateVideo(item)
        self.updateVideoAreas()

    def stop(self):
        self.player.stop()

    def addChannel(self, url, auto='', genre=''):
        self.printInfos('Add '+url)
        # Check not already present in db
        channel = self.db.getChannel(url)
        if None != channel:
            self.printInfos('"%s" already present (%s)' % \
                    (channel['url'], channel['title']))
            return False

        # Retrieve url feed
        data = backends.getData(url, self.printInfos, True)

        if None == data:
            return False

        # Add channel to db
        self.db.addChannel(url, data['title'], data['type'], genre, auto, data)

        # Update video list
        self.db.addVideos(data)

        # TODO directly update itemList without using db

        self.updateChannels(self.db.selectChannels())
        self.updateVideos(self.db.selectVideos())

        self.printInfos(data['title']+' added')

    def channelAuto(self, idx, auto=None):
        """ Switch auto value or set it to a value if argument auto is
        provided """
        channel = self.channels[idx]
        title = channel['title']

        if None == auto:
            if '' == channel['auto']:
                newValue = '.*'
            else:
                newValue = ''
        else:
            newValue = auto
        channel['auto'] = newValue
        self.printInfos('Auto for channel %s is set to: "%s"' \
                % (title, newValue))

        self.updateChannelAreas()
        self.db.updateChannel(channel)

    def updateVideoList(self, urls=None):
        self.printInfos('Update...')
        updated = False

        if None == urls:
            urls = list(map(lambda x: x['url'], self.db.selectChannels()))

        for i, url in enumerate(urls):
            channel = self.db.getChannel(url)
            self.printInfos('Update channel %s (%d/%d)...' \
                    % (channel['title'], i+1, len(urls)))

            data = backends.getData(url, self.printInfos)

            if None == data:
                continue

            # Automatic download
            if not '' == channel['auto']:
                regex = re.compile(channel['auto'])
                subdata = [ item for item in data['items'] \
                        if regex.match(item['title']) ]
                for s in subdata:
                    self.downloadManager.add(s, channel)

            updated = updated or self.db.addVideos(data)

        # TODO directly update itemList
        if updated:
            self.updateVideos(self.db.selectVideos())
