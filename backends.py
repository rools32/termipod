import os, os.path
from queue import Queue
from threading import Thread

import rss
import yt
from utils import *

def getData(url, printInfos=print, new=False):
    if 'http' != url[:4]: # local file
        data = rss.getData(url, printInfos)
    elif 'youtube' in url:
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
            worker = Thread(target=self.handleQueue)
            worker.setDaemon(True)
            worker.start()

        for video in self.itemList.videos:
            if 'download' == video['status']:
                channel = self.itemList.db.getChannel(video['url'])
                self.add(video, channel, update=False)
        self.waitDone()

    def handleQueue(self):
        """This is the worker thread function. It processes items in the queue one
        after another.  These daemon threads go into an infinite loop, and only
        exit when the main thread ends."""
        q = self.queue
        while True:
            video, channel = q.get()
            self.download(video, channel)
            q.task_done()

    def add(self, video, channel, update=True):
        if update:
            self.printInfos('Add to download: %s' % video['title'])
            video['status'] = 'download'
            self.itemList.db.updateVideo(video)
            self.itemList.updateVideoAreas()
        self.queue.put((video, channel))

    def waitDone(self):
        self.queue.join()

    def download(self, video, channel):
        link = video['link']

        # Set filename # TODO handle collision add into db even before downloading
        path = strToFilename(channel['title'])
        if not os.path.exists(path):
            os.makedirs(path)

        # Download file
        if 'rss' == channel['type']:
            ext = link.split('.')[-1]
            filename = "%s/%s_%s.%s" % (path, tsToDate(video['date']),
                    strToFilename(video['title']), ext)
            ret = rss.download(link, filename, self.printInfos)

        elif 'youtube' == channel['type']:
            filename = "%s/%s_%s.%s" % (path, tsToDate(video['date']),
                    strToFilename(video['title']), 'mp4')
            ret = yt.download(link, filename, self.printInfos)

        if 0 != ret: # Download did not happen
            self.printInfos('Download failed %s' % link)
            return

        # Change status and filename
        video['filename'] = filename
        video['status'] = 'local'
        self.itemList.db.updateVideo(video)
        self.itemList.updateVideoAreas()
