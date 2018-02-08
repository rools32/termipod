import re
import operator
import os, os.path
from threading import Thread

import backends
import player
from database import DataBase
from utils import *

class ItemList():
    def __init__(self, config, printInfos=print, wait=False):
        self.dbName = config.dbPath
        self.wait = wait
        self.db = DataBase(self.dbName, printInfos)
        self.printInfos = printInfos
        self.mediumAreas = []
        self.channelAreas = []
        self.media = []
        self.channels = []

        self.addChannels()
        self.addMedia()

        self.player = player.Player(self, self.printInfos)
        self.downloadManager = \
                backends.DownloadManager(self, self.wait, self.printInfos)

        # Mark removed files as read
        for medium in self.media:
            if 'local' == medium['location'] and not os.path.isfile(medium['filename']):
                self.remove(medium=medium, unlink=False)


    def addChannels(self, channels=None):
        if None == channels:
            channels = self.db.selectChannels()

        self.channels[0:0] = channels
        for i, c in enumerate(self.channels):
            c['index'] = i
        self.updateChannelAreas() # TODO smart

    def addMediumArea(self, area):
        self.mediumAreas.append(area)

    def addChannelArea(self, area):
        self.channelAreas.append(area)

    def addMedia(self, media=None):
        if None == media:
            self.media = []
            media = self.db.selectMedia()

        self.media[0:0] = media
        for i, v in enumerate(self.media):
            v['index'] = i

        self.updateMediumAreas(newMedia=media)

    def updateMediumAreas(self, newMedia=None, modifiedMedia=None):
        for area in self.mediumAreas:
            if None == newMedia and None == modifiedMedia:
                area.resetContents()
            else:
                if None != newMedia:
                    area.addContents(newMedia)
                if None != modifiedMedia:
                    area.updateContents(modifiedMedia)

    def updateChannelAreas(self):
        for area in self.channelAreas:
                area.resetContents()

    def add(self, medium):
        self.media.append(medium)
        self.updateStrings()

    def download(self, indices):
        if int == type(indices):
            indices = [indices]

        media = []
        for idx in indices:
            medium = self.media[idx]
            link = medium['link']

            channel = self.db.getChannel(medium['url'])
            self.downloadManager.add(medium, channel)
            media.append(medium)

    def play(self, idx):
        medium = self.media[idx]
        self.player.play(medium)

    def playadd(self, idx):
        medium = self.media[idx]
        self.player.add(medium)

    def stop(self):
        self.player.stop()

    def switchRead(self, indices, skip=False):
        if int == type(indices):
            indices = [indices]

        media = []
        for idx in indices:
            medium = self.media[idx]
            if medium['state'] in ('read', 'skipped'):
                medium['state'] = 'unread'
            else:
                if skip:
                    medium['state'] = 'skipped'
                else:
                    medium['state'] = 'read'
            self.db.updateMedium(medium)
            media.append(medium)

        self.updateMediumAreas(modifiedMedia=media)

    def remove(self, idx=None, medium=None, unlink=True):
        if idx:
            medium = self.media[idx]

        if not medium:
            return

        if unlink:
            if '' == medium['filename']:
                self.printInfos('Filename is empty')

            elif os.path.isfile(medium['filename']):
                try:
                    os.unlink(medium['filename'])
                except:
                    self.printInfos('Cannot remove "%s"' % medium['filename'])
                else:
                    self.printInfos('File "%s" removed' % medium['filename'])
            else:
                self.printInfos('File "%s" is absent' % medium['filename'])

        self.printInfos('Mark "%s" as local and read' % medium['title'])
        medium['state'] = 'read'
        medium['location'] = 'remote'
        self.db.updateMedium(medium)

        self.updateMediumAreas(modifiedMedia=[medium])

    def newChannel(self, url, auto='', genre=''):
        self.printInfos('Add '+url)
        # Check not already present in db
        channel = self.db.getChannel(url)
        if None != channel:
            self.printInfos('"%s" already present (%s)' % \
                    (channel['url'], channel['title']))
            return False

        thread = Thread(target = self.newChannelTask, args = (url, genre, auto))
        thread.daemon = True
        thread.start()
        if self.wait:
            thread.join()

    def newChannelTask(self, url, genre, auto):
        # Retrieve url feed
        data = backends.getData(url, self.printInfos, True)

        if None == data:
            return False

        # Add channel to db
        data['genre'] = genre
        data['auto'] = auto
        updated = data['updated']
        data['updated'] = 0 # set to 0 in db for addMedia
        self.db.addChannel(data)
        data['updated'] = updated

        # Update medium list
        media = self.db.addMedia(data)

        self.addChannels([data])
        self.addMedia(media)

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

    def updateMediumList(self, urls=None):
        self.printInfos('Update...')
        if None == urls:
            urls = list(map(lambda x: x['url'], self.db.selectChannels()))

        thread = Thread(target = self.updateTask, args = (urls, ))
        thread.daemon = True
        thread.start()
        if self.wait:
            thread.join()

    def updateTask(self, urls):
        allNewMedia = []

        needToWait = False
        for i, url in enumerate(urls):
            channel = self.db.getChannel(url)
            self.printInfos('Update channel %s (%d/%d)...' \
                    % (channel['title'], i+1, len(urls)))

            data = backends.getData(url, self.printInfos)

            if None == data:
                continue

            newMedia = self.db.addMedia(data)
            if not len(newMedia):
                continue

            allNewMedia = newMedia+allNewMedia

            # Automatic download
            if not '' == channel['auto']:
                regex = re.compile(channel['auto'])
                subMedia = [ medium for medium in newMedia \
                        if regex.match(medium['title']) ]
                for s in subMedia:
                    self.downloadManager.add(s, channel)
                    needToWait = True
        self.printInfos('Update channels done!')

        allNewMedia.sort(key=operator.itemgetter('date'), reverse=True)
        self.addMedia(allNewMedia)

        if self.wait and needToWait:
            self.printInfos('Wait for downloads to complete...')
            self.downloadManager.waitDone()

