import re

import backends
import player
from database import DataBase
from utils import *

class ItemList():
    def __init__(self, dbName, printInfos=print):
        self.dbName = dbName
        self.db = DataBase(dbName)
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

    def download(self, idx):
        item = self.videos[idx]
        link = item['link']

        channel = self.db.getChannel(item['url'])
        self.downloadManager.add(item, channel)
        self.db.updateVideo(item)
        self.updateVideoAreas()

    def play(self, idx):
        item = self.videos[idx]
        self.player.play(item)

    def playadd(self, idx):
        item = self.videos[idx]
        self.player.add(item)

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

    def updateVideoList(self, urls=None):
        self.printInfos('Update...')
        updated = False

        if None == urls:
            urls = list(map(lambda x: x['url'], self.db.selectChannels()))

        for url in urls:
            channel = self.db.getChannel(url)

            data = backends.getData(url, self.printInfos)

            if None == data:
                continue

            # Automatic download
            if not '' == channel['auto']:
                regex = re.compile(channel['auto'])
                subdata = [ item for item in data['items'] if regex.match(item['title']) ]
                for s in subdata:
                    self.downloadManager.add(s, channel)

            updated = updated or self.db.addVideos(data)

        # TODO directly update itemList
        if updated:
            self.updateVideos(db.selectVideos())
