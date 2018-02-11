# -*- coding: utf-8 -*-
#
# termipod
# Copyright (c) 2018 Cyril Bordage
#
# termipod is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# termipod is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
import os
from time import sleep

import mpv

from termipod.utils import *


class Player():
    def __init__(self, item_list, print_infos=print):
        self.item_list = item_list
        self.print_infos = print_infos
        self.player = None
        self.current_filename = None
        self.playlist = {}

    def start(self):
        self.player = \
            mpv.MPV(log_handler=self.mpv_log, ytdl=True,
                    input_default_bindings=True, input_vo_keyboard=True,
                    osc=True, config=True)
        self.player.force_window = True
        self.player.keep_open = 'always'
        self.player.keep_open_pause = False  # To continue after next file

        @self.player.on_key_press('?')
        def help():
            separator = u" \u2022 "
            help_msg = ''
            help_msg += 'Added keys:'
            help_msg += '\n'
            help_msg += separator+"'r' to mark as read"
            help_msg += '\n'
            help_msg += separator+"'d' to mark as read, delete and play next"
            help_msg += '\n'
            help_msg += '\n'
            help_msg += separator+"File auto marked as read if fully read"
            help_msg += '\n'
            help_msg += \
                separator+"'>' to go to next file without marking as read"

            # If help is not shown we show it
            if help_msg != self.player.osd_msg1:
                self.player.osd_msg1 = help_msg

            # we hide help msg
            else:
                self.player.osd_msg1 = ''

        @self.player.on_key_press('q')
        def stop():
            self.stop()

        @self.player.on_key_press('d')
        def remove_and_next():
            self.mark_as_played(unlink=True)
            self.next()

        @self.player.on_key_press('r')
        def read_and_next():
            self.mark_as_played()
            self.next()

        @self.player.property_observer('eof-reached')
        def update_played(_name, value):
            if value:  # can be True thanks to keep_open
                read_and_next()

        @self.player.property_observer('stream-path')
        def update_played(_name, value):
            self.current_filename = value

    def mpv_log(self, loglevel, component, message):
        print_log(message)

    def mark_as_played(self, unlink=False):
        db = self.item_list.db
        medium = self.playlist[self.current_filename]
        medium['state'] = 'read'
        self.print_infos('Mark as read %s' % medium['filename'])

        if unlink:
            self.print_infos('Remove %s' % medium['filename'])
            os.unlink(medium['filename'])
            medium['filename'] = ''

        db.update_medium(medium)
        self.item_list.update_medium_areas()

    def play(self, medium, now=True):
        if now:
            self.print_infos('Play '+medium['title'])
        else:
            self.print_infos('Enqueue '+medium['title'])

        if not self.player:
            self.start()

        if 'local' == medium['location'] and '' != medium['filename']:
            target = medium['filename']
        else:
            target = medium['link']

        self.playlist[target] = medium
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

    def add(self, medium):
        self.play(medium, now=False)

    def stop(self):
        if self.player:
            self.player.write_watch_later_config()
            self.player.terminate()
            del self.player
            self.player = None
