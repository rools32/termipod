import urllib.request
import os, os.path

from utils import *

class ItemList():
    def __init__(self, items, db, printInfos):
        self.items = items
        self.db = db
        self.printInfos = printInfos
        self.tabs = None

    def setTabx(self, tabs):
        self.tabs = tabs

    def update(self, items=None):
        if None == items:
            items = self.db.selectVideos()
        self.items = items

    def toString(self, status, width):
        return list(map(lambda x: self.itemToString(x, width),
                        self.getItems(status)))

    def itemToString(self, item, width):
        date = tsToDate(item['date'])
        duration = durationToStr(item['duration'])
        separator = u" \u2022 "
        lastSeparator = " "

        string = date
        string += separator
        string += item['channel']
        string += separator
        string += item['title']

        # Truncate the line or add spaces if needed
        space = width-1-len(string+lastSeparator+duration)
        if space < 0:
            string = string[:space-3]
            string += '...'
        else:
            string += ' '*space

        string += lastSeparator
        string += duration

        return string

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
        if self.tabs:
            self.tabs.updateAreas()

    def getItems(self, status):
        return [ v for v in self.items if v['status'] == status ]

