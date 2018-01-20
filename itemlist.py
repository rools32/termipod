import urllib.request
import os, os.path

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

        if 'rss' == channel['type']:
            ext = link.split('.')[-1]
            filename = "%s/%s_%s.%s" % (path, tsToDate(item['date']),
                    strToFilename(item['title']), ext)

            # Download file TODO background
            self.printInfos("Download "+link)
            urllib.request.urlretrieve(link, filename)

        elif 'yt' == channel['type']:
            pass

        # Change status and filename
        self.db.makrAsDownloaded(item['url'], item['title'],
                item['date'], filename)
        item['filename'] = filename
        item['status'] = 'downloaded'
        self.updatesAreas()
