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
        self.printInfos = printInfos
        self.videoAreas = []
        self.channelAreas = []
        self.videos = []
        self.channels = []

        self.addChannels()
        self.addVideos()

        self.player = player.Player(self, self.printInfos)
        self.downloadManager = \
                backends.DownloadManager(self, self.wait, self.printInfos)

        # Mark removed files as read
        for video in self.videos:
            if 'local' == video['location'] and not os.path.isfile(video['filename']):
                self.remove(video=video, unlink=False)


    def addChannels(self, channels=None, replace=True):
        if None == channels:
            channels = self.db.selectChannels()

        if replace:
            self.channels.clear()

        self.channels[0:0] = channels
        for i, c in enumerate(self.channels):
            c['index'] = i
        self.updateChannelAreas() # TODO smart if !replace

    def addVideoArea(self, area):
        self.videoAreas.append(area)

    def addChannelArea(self, area):
        self.channelAreas.append(area)

    def addVideos(self, videos=None, replace=False):
        if None == videos:
            self.videos = []
            videos = self.db.selectVideos()

        if replace:
            self.videos.clear()

        self.videos[0:0] = videos
        for i, v in enumerate(self.videos):
            v['index'] = i

        if replace:
            self.updateVideoAreas()
        else:
            self.updateVideoAreas(newVideos=videos)

    def updateVideoAreas(self, newVideos=None, modifiedVideos=None):
        for area in self.videoAreas:
            if None == newVideos and None == modifiedVideos:
                area.resetContents()
            else:
                if None != newVideos:
                    area.addContents(newVideos)
                if None != modifiedVideos:
                    area.updateContents(modifiedVideos)

    def updateChannelAreas(self):
        for area in self.channelAreas:
                area.resetContents()

    def add(self, video):
        self.videos.append(video)
        self.updateStrings()

    def download(self, indices):
        if int == type(indices):
            indices = [indices]

        videos = []
        for idx in indices:
            video = self.videos[idx]
            link = video['link']

            channel = self.db.getChannel(video['url'])
            self.downloadManager.add(video, channel)
            videos.append(video)

    def play(self, idx):
        video = self.videos[idx]
        self.player.play(video)

    def playadd(self, idx):
        video = self.videos[idx]
        self.player.add(video)

    def stop(self):
        self.player.stop()

    def switchRead(self, indices, skip=False):
        if int == type(indices):
            indices = [indices]

        videos = []
        for idx in indices:
            video = self.videos[idx]
            if video['state'] in ('read', 'skipped'):
                video['state'] = 'unread'
            else:
                if skip:
                    video['state'] = 'skipped'
                else:
                    video['state'] = 'read'
            self.db.updateVideo(video)
            videos.append(video)

        self.updateVideoAreas(modifiedVideos=videos)

    def remove(self, idx=None, video=None, unlink=True):
        if idx:
            video = self.videos[idx]

        if not video:
            return

        if unlink:
            if '' == video['filename']:
                self.printInfos('Filename is empty')

            elif os.path.isfile(video['filename']):
                try:
                    os.unlink(video['filename'])
                except:
                    self.printInfos('Cannot remove "%s"' % video['filename'])
                else:
                    self.printInfos('File "%s" removed' % video['filename'])
            else:
                self.printInfos('File "%s" is absent' % video['filename'])

        self.printInfos('Mark "%s" as local and read' % video['title'])
        video['state'] = 'read'
        video['location'] = 'remote'
        self.db.updateVideo(video)

        self.updateVideoAreas(modifiedVideos=[video])

    def newChannel(self, url, auto='', genre=''):
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

        self.addChannels([data], replace=False)
        self.addVideos(videos, replace=False)

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
        self.printInfos('Update channels done!')

        if self.wait and needToWait:
            self.printInfos('Wait for downloads to complete...')
            self.downloadManager.waitDone()

        allNewVideos.sort(key=operator.itemgetter('date'), reverse=True)
        self.addVideos(allNewVideos)
