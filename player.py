import mpv
import os
from time import sleep

from utils import *

class Player():
    def __init__(self, itemList, printInfos=print):
        self.itemList = itemList
        self.printInfos = printInfos
        self.player = None
        self.currentFilename = None
        self.playlist = {}

    def start(self):
        self.player = mpv.MPV(log_handler=self.mpv_log, ytdl=True,
                input_default_bindings=True, input_vo_keyboard=True,
                osc=True, config=True)
        self.player.force_window = True
        self.player.keep_open = 'always'
        self.player.keep_open_pause = False # To continue after next file

        @self.player.on_key_press('?')
        def help():
            separator = u" \u2022 "
            helpMsg = ''
            helpMsg += 'Added keys:'
            helpMsg += '\n'
            helpMsg += separator+"'r' to mark as read"
            helpMsg += '\n'
            helpMsg += separator+"'d' to mark as read, delete and play next"
            helpMsg += '\n'
            helpMsg += '\n'
            helpMsg += separator+"File auto marked as read if fully read"
            helpMsg += '\n'
            helpMsg += separator+"'>' to go to next file without marking as read"

            # If help is not shown we show it
            if helpMsg != self.player.osd_msg1:
                self.player.osd_msg1 = helpMsg

            # we hide help msg
            else:
                self.player.osd_msg1 = ''

        @self.player.on_key_press('q')
        def stop():
            self.stop()

        @self.player.on_key_press('d')
        def remove_and_next():
            self.markAsPlayed(unlink=True)
            self.next()

        @self.player.on_key_press('r')
        def read_and_next():
            self.markAsPlayed()
            self.next()

        @self.player.property_observer('eof-reached')
        def updatePlayed(_name, value):
            if value: # can be True thanks to keep_open
                read_and_next()

        @self.player.property_observer('stream-path')
        def updatePlayed(_name, value):
            self.currentFilename = value

    def mpv_log(self, loglevel, component, message):
        printLog(message)

    def markAsPlayed(self, unlink=False):
        db = self.itemList.db
        video = self.playlist[self.currentFilename]
        video['state'] = 'read'
        self.printInfos('Mark as read %s' % video['filename'])

        if unlink:
            self.printInfos('Remove %s' % video['filename'])
            os.unlink(video['filename'])
            video['filename'] = ''

        db.updateVideo(video)
        self.itemList.updateVideoAreas()

    def play(self, video, now=True):
        if now:
            self.printInfos('Play '+video['title'])
        else:
            self.printInfos('Enqueue '+video['title'])

        if not self.player:
            self.start()

        if 'local' == video['location'] and '' != video['filename']:
            target=video['filename']
        else:
            target=video['link']

        self.playlist[target] = video
        self.player.loadfile(target, 'append-play')
        if now:
            self.player.playlist_pos = self.player.playlist_count-1

    def next(self):
        if self.player.playlist_pos+1 == self.player.playlist_count:
            self.stop()
        else:
            self.player.playlist_next(mode='force')

    def prev(self):
        self.player.playlist_prev(mode='force')

    def add(self, video):
        self.play(video, now=False)

    def stop(self):
        if self.player:
            #self.player.quit_watch_later()
            self.player.write_watch_later_config() # FIXME do not work
            self.player.terminate()
            del self.player
            self.player = None
