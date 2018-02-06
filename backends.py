import os, os.path
import shlex
from time import sleep
from queue import Queue
from threading import Thread
import subprocess

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

def getDuration(medium):
    filename = os.path.abspath(medium['filename']).replace('"','\\"')
    commandline = 'ffprobe -i "%s" -show_entries format=duration -v quiet -of csv="p=0"' % filename
    args = shlex.split(commandline)
    result = subprocess.Popen(args,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    output = result.communicate()
    duration = int(float(output[0]))
    return duration

class DownloadManager():
    def __init__(self, itemList, wait=False, printInfos=print):
        self.nthreads = 2
        self.itemList = itemList
        self.printInfos = printInfos
        self.queue = Queue()
        self.wait = wait
        self.maxRetries = 3

        # Set up some threads to fetch the items to download
        for i in range(self.nthreads):
            worker = Thread(target=self.handleQueue)
            worker.setDaemon(True)
            worker.start()

        for medium in self.itemList.media:
            if 'download' == medium['location']:
                channel = self.itemList.db.getChannel(medium['url'])
                self.add(medium, channel, update=False)
        if self.wait:
            self.waitDone()

    def handleQueue(self):
        """This is the worker thread function. It processes items in the queue one
        after another.  These daemon threads go into an infinite loop, and only
        exit when the main thread ends."""
        q = self.queue
        while True:
            medium, channel = q.get()
            ret = self.download(medium, channel)
            q.task_done()
            if None == ret:
                if not medium['link'] in self.handleQueue.retries:
                    self.handleQueue.retries[medium['link']] = 1

                if self.maxRetries <= self.handleQueue.retries[medium['link']]:
                    continue

                self.handleQueue.retries[medium['link']] += 1
                sleep(5)
                self.add(medium, channel, update=False)
    handleQueue.retries = {}


    def add(self, medium, channel, update=True):
        if update:
            self.printInfos('Add to download: %s' % medium['title'])
            medium['location'] = 'download'
            self.itemList.db.updateMedium(medium)
            self.itemList.updateMediumAreas(modifiedMedia=[medium])
        self.queue.put((medium, channel))

    def waitDone(self):
        self.queue.join()

    def download(self, medium, channel):
        link = medium['link']

        # Set filename # TODO handle collision
        path = strToFilename(channel['title'])
        if not os.path.exists(path):
            os.makedirs(path)

        # Download file
        self.printInfos('Download %s...' % medium['title'])
        if 'rss' == channel['type']:
            ext = link.split('.')[-1]
            filename = "%s/%s_%s.%s" % (path, tsToDate(medium['date']),
                    strToFilename(medium['title']), ext)
            ret = rss.download(link, filename, self.printInfos)

        elif 'youtube' == channel['type']:
            filename = "%s/%s_%s.%s" % (path, tsToDate(medium['date']),
                    strToFilename(medium['title']), 'mp4')
            ret = yt.download(link, filename, self.printInfos)

        if 0 != ret: # Download did not happen
            self.printInfos('Download failed %s' % link)
            return

        # Change location and filename
        medium['filename'] = filename
        medium['location'] = 'local'

        if 0 == medium['duration']:
            medium['duration'] = getDuration(medium)

        self.itemList.db.updateMedium(medium)
        self.itemList.updateMediumAreas(modifiedMedia=[medium])

        return 0
