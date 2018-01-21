import os, os.path
import rss
import yt

from utils import *

class ItemList():
    def __init__(self, items, db, printInfos):
        self.items = items
        self.db = db
        self.printInfos = printInfos
        self.areas = []

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
        # Set filename # TODO handle collision add into db even before downloading
        channel = self.db.getChannel(item['url'])
        path = strToFilename(channel['title'])
        if not os.path.exists(path):
            os.makedirs(path)

        self.printInfos("Download "+link)
        # Download file TODO background
        if 'rss' == channel['type']:
            ext = link.split('.')[-1]
            filename = "%s/%s_%s.%s" % (path, tsToDate(item['date']),
                    strToFilename(item['title']), ext)
            rss.download(link, filename)

        elif 'youtube' == channel['type']:
            filename = "%s/%s_%s.%s" % (path, tsToDate(item['date']),
                    strToFilename(item['title']), 'mp4')
            yt.download(link, filename)

        # Change status and filename
        self.db.makrAsDownloaded(item['url'], item['title'],
                item['date'], filename)
        item['filename'] = filename
        item['status'] = 'downloaded'
        self.updatesAreas()

    def addChannel(self, url, auto=False, genre=None):
        # Check not already present in db
        channel = self.db.getChannel(url)
        if None != channel:
            return '"%s" already present' % channel['title']

        # Retrieve url feed
        if 'youtube' in url:
            data = yt.getData(url, True)
        else:
            data = rss.getData(url)

        # Add channel to db
        self.db.addChannel(url, data['title'], data['type'], genre, auto, data)

        # Update video list
        self.db.addVideos(data)

        # TODO directly update itemList

        self.update(self.db.selectVideos())

        return data['title']+' added'

    def updateVideos(self, urls=None):
        updated = False
        if None == urls:
            urls = list(map(lambda x: x['url'], self.db.selectChannels()))
        for url in urls:
            channel = self.db.getChannel(url)
            if 'youtube' == channel['type']:
                data = yt.getData(url)
            elif 'rss' == channel['type']:
                data = rss.getData(url)

            if data:
                updated = updated or self.db.addVideos(data)
        # TODO directly update itemList
        return updated
