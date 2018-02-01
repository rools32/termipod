import re
import operator
import os, os.path

import backends
import player
from database import DataBase
from utils import *

class ItemList():
    def __init__(self, dbName, printInfos=print, wait=False):
        self.dbName = dbName
        self.wait = wait
        self.db = DataBase(dbName, printInfos)
        self.videos = self.db.selectVideos()
        self.channels = self.db.selectChannels()
        self.printInfos = printInfos
        self.videoAreas = []
        self.channelAreas = []
        self.player = player.Player(self, self.printInfos)
        self.downloadManager = backends.DownloadManager(self, self.printInfos)

    def updateChannels(self, channels=None, replace=True):
        if None == channels:
            channels = self.db.selectVideos()

        if replace:
            self.channels.clear()

        self.channels[0:0] = channels
        self.updateChannelAreas() # TODO smart if !replace

    def updateVideos(self, videos=None, replace=True):
        if None == videos:
            videos = self.db.selectVideos()

        if replace:
            self.videos.clear()

        self.videos[0:0] = videos
        self.updateVideoAreas() # TODO smart if !replace

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

    def remove(self, idx=None, video=None, unlink=True):
        if idx:
            video = self.videos[idx]

        if not video:
            return

        if unlink:
            self.printInfos('Remove "%s" file' % video['filename'])
            os.unlink(video['filename'])

        self.printInfos('Mark "%s" as local and read' % video['title'])
        video['state'] = 'read'
        video['status'] = 'remote'
        self.db.updateVideo(video)

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
        data['genre'] = genre
        data['auto'] = auto
        updated = data['updated']
        data['updated'] = 0 # set to 0 in db for addVideos
        self.db.addChannel(data)
        data['updated'] = updated

        # Update video list
        videos = self.db.addVideos(data)

        self.updateChannels([data], replace=False)
        self.updateVideos(videos, replace=False)

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
        allNewVideos = []

        if None == urls:
            urls = list(map(lambda x: x['url'], self.db.selectChannels()))

        needToWait = False
        for i, url in enumerate(urls):
            channel = self.db.getChannel(url)
            self.printInfos('Update channel %s (%d/%d)...' \
                    % (channel['title'], i+1, len(urls)))

            data = backends.getData(url, self.printInfos)

            if None == data:
                continue

            newVideos = self.db.addVideos(data)
            if not len(newVideos):
                continue

            allNewVideos = newVideos+allNewVideos

            # Automatic download
            if not '' == channel['auto']:
                regex = re.compile(channel['auto'])
                subVideos = [ video for video in newVideos \
                        if regex.match(video['title']) ]
                for s in subVideos:
                    self.downloadManager.add(s, channel)
                    needToWait = True

        if self.wait and needToWait:
            self.printInfos('Wait for downloads to complete...')
            self.downloadManager.waitDone()

        allNewVideos.sort(key=operator.itemgetter('date'), reverse=True)
        self.updateVideos(allNewVideos, replace=False)
