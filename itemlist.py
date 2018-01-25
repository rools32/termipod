import re

import backends
import player
from database import DataBase
from utils import *

class ItemList():
    def __init__(self, dbName, printInfos=print):
        self.dbName = dbName
        self.db = DataBase(dbName)
        self.items = self.db.selectVideos()
        self.printInfos = printInfos
        self.areas = []
        self.player = player.Player(self, self.printInfos)
        self.downloadManager = backends.DownloadManager(self.printInfos)

    def update(self, items=None):
        if None == items:
            items = self.db.selectVideos()
        self.items.clear()
        self.items.extend(items)
        self.updatesAreas()

    def updatesAreas(self):
        for area in self.areas:
            area.resetContent()

    def add(self, item):
        self.items.append(item)
        self.updateStrings()

    def download(self, idx):
        item = self.items[idx]
        link = item['link']

        channel = self.db.getChannel(item['url'])
        backends.download(item, channel, self.printInfos)
        self.db.updateItem(item)
        self.updatesAreas()

    def play(self, idx):
        item = self.items[idx]
        self.player.play(item)

    def playadd(self, idx):
        item = self.items[idx]
        self.player.add(item)

    def stop(self):
        self.player.stop()

    def addChannel(self, url, auto='', genre=None):
        self.printInfos('Add '+url)
        # Check not already present in db
        channel = self.db.getChannel(url)
        if None != channel:
            return '"%s" already present' % channel['title']

        # Retrieve url feed
        data = backends.getData(url, self.printInfos, True)

        # Add channel to db
        self.db.addChannel(url, data['title'], data['type'], genre, auto, data)

        # Update video list
        self.db.addVideos(data)

        # TODO directly update itemList without using db

        self.update(self.db.selectVideos())

        self.printInfos(data['title']+' added')

    def updateVideos(self, urls=None):
        self.printInfos('Update...')
        updated = False

        if None == urls:
            urls = list(map(lambda x: x['url'], self.db.selectChannels()))

        for url in urls:
            channel = self.db.getChannel(url)

            data = backends.getData(url, self.printInfos)

            # Automatic download
            if not '' == channel['auto']:
                regex = re.compile(channel['auto'])
                subdata = [ item for item in data['items'] if regex.match(item['title']) ]
                for s in subdata:
                    backends.download(s, channel, self.printInfos)

            if data:
                updated = updated or self.db.addVideos(data)
        # TODO directly update itemList
        if updated:
            self.update(db.selectVideos())
