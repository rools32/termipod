import os, os.path
from queue import Queue
from threading import Thread

import rss
import yt
from utils import *


def getData(url, printInfos=print, new=False):
    if 'youtube' in url:
        data = yt.getData(url, printInfos, new)
    else:
        data = rss.getData(url, printInfos)
    return data

class DownloadManager():
    def __init__(self, itemList, printInfos=print):
        self.nthreads = 2
        self.itemList = itemList
        self.printInfos = printInfos
        self.queue = Queue()

        # Set up some threads to fetch the items to download
        for i in range(self.nthreads):
            worker = Thread(target=self.handleQueue, args=(self.queue,))
            worker.setDaemon(True)
            worker.start()

        for item in self.itemList.items:
            if 'downloading' == item['status']:
                channel = self.itemList.db.getChannel(item['url'])
                self.add(item, channel, update=False)

    def handleQueue(self, q):
        """This is the worker thread function. It processes items in the queue one
        after another.  These daemon threads go into an infinite loop, and only
        exit when the main thread ends."""
        while True:
            item, channel = q.get()
            self.download(item,channel)
            q.task_done()

    def add(self, item, channel, update=True):
        if update:
            self.printInfos('Add to download: %s' % item['title'])
            item['status'] = 'downloading'
            self.itemList.db.updateItem(item)
            self.itemList.updatesAreas()
        self.queue.put((item, channel))

    def download(self, item, channel):
        link = item['link']

        # Set filename # TODO handle collision add into db even before downloading
        path = strToFilename(channel['title'])
        if not os.path.exists(path):
            os.makedirs(path)

        # Download file
        if 'rss' == channel['type']:
            ext = link.split('.')[-1]
            filename = "%s/%s_%s.%s" % (path, tsToDate(item['date']),
                    strToFilename(item['title']), ext)
            rss.download(link, filename, self.printInfos)

        elif 'youtube' == channel['type']:
            filename = "%s/%s_%s.%s" % (path, tsToDate(item['date']),
                    strToFilename(item['title']), 'mp4')
            yt.download(link, filename, self.printInfos)

        # Change status and filename
        item['filename'] = filename
        item['status'] = 'downloaded'
        db = DataBase(self.itemList.dbName)
        db.updateItem(item)
        self.itemList.updatesAreas()
