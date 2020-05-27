# -*- coding: utf-8 -*-
#
# termipod
# Copyright (c) 2020 Cyril Bordage
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
import curses
import curses.textpad
import os
import re
import time
import shlex
from bisect import bisect
from threading import Lock, Thread
from sys import stderr
from queue import Queue
from time import sleep
from datetime import datetime
from collections import deque

from termipod.utils import (duration_to_str, ts_to_date, print_log,
                            format_string, printable_str,
                            commastr_to_list, list_to_commastr,
                            screen_reset)
from termipod.itemlist import ItemList
from termipod.keymap import (Keymap, get_key, get_key_name, get_key_code,
                             get_last_key, init_key_tables, get_keymap)
from termipod.database import DataBaseVersionException
from termipod.httpserver import HTTPServer
from termipod.completer import CommaListCompleter, CommandCompleter


class UI():
    def __init__(self, config):
        screen = curses.initscr()
        self.screen = screen
        screen.keypad(1)  # to handle special keys as one key
        screen.immedok(True)
        curses.start_color()
        curses.curs_set(0)  # disable cursor
        curses.cbreak()  # no need to press enter to react to keys
        curses.noecho()  # do not show pressed keys
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_GREEN, -1)
        curses.init_pair(2, -1, -1)
        curses.init_pair(3, curses.COLOR_RED, -1)
        try:
            curses.init_pair(4, 8, -1)  # Grey
        except curses.error:
            curses.init_pair(4, -1, -1)
        screen.refresh()

        init_key_tables(screen)
        self.keymap = Keymap(config)

        self.status_area = StatusArea(screen, print_popup=self.print_popup,
                                      print_terminal=self.print_terminal)
        try:
            self.item_list = ItemList(config, print_infos=self.print_infos)
        except DataBaseVersionException as e:
            curses.endwin()
            print(e, file=stderr)
            exit(1)

        tabs = Tabs(screen, self.item_list, self.print_infos)
        self.tabs = tabs

        # New tabs
        tabs.add_media('remote', 'Remote media')
        tabs.add_media('local', 'Local media')
        tabs.add_media('download', 'Downloading')
        tabs.add_channels('channels', 'Channels')
        tabs.show_tab(0)

        # Run update thread
        self.update_minutes = int(config.update_minutes)
        thread = Thread(target=self.update_channels_task)
        thread.daemon = True
        thread.start()

        # Run download maæger
        self.item_list.download_manager_init(cb=tabs.update_areas,
                                             dl_marked=False)

        # Init player
        self.item_list.player_init(cb=tabs.update_areas)

        # Prepare http server (do not run it)
        self.httpserver = HTTPServer(int(config.httpserver_port),
                                     self.print_infos)

        while True:
            # Wait for key
            key_code = get_key(screen)
            key_name = get_key_name(key_code)
            area = tabs.get_current_area()

            area_key_class = area.get_key_class()
            idx = area.get_idx()

            action = self.keymap.get_action(area_key_class, key_name)
            print_log(action)

            if action is None:
                self.print_infos("Key '%r' not mapped for %s" %
                                 (key_name, area_key_class))

            ###################################################################
            # All tab commands
            ###################################################################

            elif 'line_down' == action:
                tabs.move_screen('line', 'down')
            elif 'line_up' == action:
                tabs.move_screen('line', 'up')
            elif 'page_down' == action:
                tabs.move_screen('page', 'down')
            elif 'page_up' == action:
                tabs.move_screen('page', 'up')
            elif 'bottom' == action:
                tabs.move_screen('all', 'down')
            elif 'top' == action:
                tabs.move_screen('all', 'up')

            elif 'screen_infos' == action:
                tabs.screen_infos()

            elif 'tab_next' == action:
                tabs.show_next_tab()

            elif 'tab_prev' == action:
                tabs.show_next_tab(reverse=True)

            elif 'help' == action:
                area.show_help(self.keymap)

            elif 'refresh' == action:
                self.refresh()

            elif 'infos' == action:
                area.show_infos()

            elif 'description' == action:
                area.show_description()

            elif 'command_get' == action:
                completer = CommandCompleter()

                completer.add_command('add', 'Add a channel')
                completer.add_option(
                    ['add'], 'url', '', '[^ ]+', 'URL', position=0)
                completer.add_option(
                    ['add'], 'count', 'count=', 'count=[-0-9]+',
                    'Maximal number of elements to retrieve info')
                completer.add_option(
                    ['add'], 'force', 'force', 'force',
                    'Force creation if already exists')
                completer.add_option(
                    ['add'], 'strict', 'strict', 'strict',
                    'Do no retrieve list of files after count')
                completer.add_option(
                    ['add'], 'auto', 'auto=', 'auto=[^ ]+',
                    'Regex for files to download automatically')
                completer.add_option(
                    ['add'], 'categories', 'categories=', 'categories=[^ ]+',
                    'Comma separated list of categories (use quotes)')
                completer.add_option(
                    ['add'], 'name', 'name=', 'name=[^ ]+',
                    'Alternative name of the channel (needed with force)')

                completer.add_command('addvideo',
                                      'Add a video (to a new disabled channel)')
                completer.add_option(
                    ['addvideo'], 'url', '', '[^ ]+', 'URL', position=0)
                completer.add_option(
                    ['addvideo'], 'force', 'force', 'force',
                    'Force creation if already exists')
                completer.add_option(
                    ['addvideo'], 'categories', 'categories=',
                    'categories=[^ ]+',
                    'Comma separated list of categories (use quotes)')
                completer.add_option(
                    ['addvideo'], 'name', 'name=', 'name=[^ ]+',
                    'Alternative name of the channel')

                completer.add_command(
                    'channelRemove',
                    'Remove selected channels (and all associated media)')

                completer.add_command('channelDisable',
                                      'Disable selected channels')

                completer.add_command('channelEnable',
                                      'Enable selected channels')

                completer.add_command('help', 'Show help')

                completer.add_command('messages', 'Print last messages')
                completer.add_option(
                    ['messages'], 'file', '', '.*', 'Output file')

                completer.add_command('errors', 'Print last errors')
                completer.add_option(
                    ['errors'], 'file', '', '.*', 'Output file')

                completer.add_command(
                    'httpServerStart',
                    'Start http streaming server')
                completer.add_option(
                    ['httpServerStart'], 'port', '', '[0-9]+', 'Port')

                completer.add_command('httpServerStop', 'Stop the server')

                completer.add_command('httpServerStatus',
                                      'Get streaming server status')

                completer.add_command('quit', 'Quit termipod')

                # TODO generate help for show_command_help from completer
                string = self.status_area.run_command(':', completer=completer)
                if string is None:
                    continue

                try:
                    command = shlex.split(string)
                except ValueError as e:
                    self.print_infos(f'Error in command: {e}', mode='error')
                    continue

                if not command:
                    self.print_infos('No command to run', mode='direct')
                    continue

                if command[0] in ('q', 'quit'):
                    curses.endwin()
                    exit()

                elif command[0] in ('h', 'help'):
                    area.show_command_help()

                elif command[0] in ('errors', ):
                    if len(command) == 2:
                        file = command[1]
                    else:
                        file = None
                    self.status_area.print_errors(file)

                elif command[0] in ('messages', ):
                    if len(command) == 2:
                        file = command[1]
                    else:
                        file = None
                    self.status_area.print_all_messages(file)

                elif command[0] in ('add',):
                    if len(command) == 1:
                        area.show_command_help('add', error=True)
                    else:
                        url = command[1]
                        start = len(command[0])+1
                        opts = string[start:].lstrip()[len(url)+1:].lstrip()
                        callback = tabs.update_areas
                        self.item_list.new_channel(url, opts, callback)

                elif command[0] in ('addvideo',):
                    if len(command) == 1:
                        area.show_command_help('addvideo', error=True)
                    else:
                        url = command[1]
                        start = len(command[0])+1
                        opts = string[start:].lstrip()[len(url)+1:].lstrip()
                        callback = tabs.update_areas

                        self.item_list.new_video(url, opts, callback)

                elif command[0] in ('channelDisable',):
                    if len(command) != 1:
                        area.show_command_help('channelDisable', error=True)
                    elif area.key_class != 'channels':
                        self.print_infos('Not in channel area')

                    else:
                        sel = self.get_user_selection(idx, area)
                        channels = self.item_list.disable_channels('ui', sel)
                        tabs.update_areas('channel', 'removed', channels,
                                          only=True)

                elif command[0] in ('channelEnable',):
                    if len(command) != 1:
                        area.show_command_help('channelEnable', error=True)
                    elif area.key_class != 'channels':
                        self.print_infos('Not in channel area')

                    else:
                        sel = self.get_user_selection(idx, area)
                        channels = self.item_list.disable_channels('ui', sel,
                                                                   enable=True)
                        tabs.update_areas('channel', 'removed', channels,
                                          only=True)

                elif command[0] in ('channelRemove',):
                    if len(command) != 1:
                        area.show_command_help('channelRemove', error=True)
                    elif area.key_class != 'channels':
                        self.print_infos('Not in channel area')
                    else:
                        sel = self.get_user_selection(idx, area)
                        channels = self.item_list.remove_channels('ui', sel)
                        tabs.update_areas('channel', 'removed', channels)

                # HTTP server
                elif command[0] in ('httpServerStart',):
                    if len(command) == 2:
                        port = command[1]
                    elif len(command) == 1:
                        port = None
                    else:
                        area.show_command_help('httpServerStart', error=True)
                        continue
                    self.httpserver.start(port)

                elif command[0] in ('httpServerStop',):
                    if len(command) != 1:
                        area.show_command_help('httpServerStop', error=True)
                    else:
                        self.httpserver.stop()

                elif command[0] in ('httpServerStatus',):
                    if len(command) != 1:
                        area.show_command_help('httpServerStatus', error=True)
                    else:
                        self.httpserver.status()

                else:
                    self.print_infos('Command "%s" not found' % command[0],
                                     mode='error')

            elif 'search_get' == action:
                search_string = self.status_area.run_command('/')
                if search_string is None:
                    continue

                if not search_string:
                    self.print_infos('No search pattern provided')
                    continue
                self.print_infos('Search: '+search_string)
                tabs.highlight(search_string)
            elif 'search_next' == action:
                tabs.next_highlight()
            elif 'search_prev' == action:
                tabs.next_highlight(reverse=True)

            elif 'quit' == action:
                break

            elif 'select_item' == action:
                tabs.select_item()
            elif 'select_until' == action:
                tabs.select_until()
            elif 'select_clear' == action:
                tabs.select_clear()

            elif 'filter_clear' == action:
                tabs.filter_clear()

            ###################################################################
            # Allmedia commands
            ###################################################################
            # Highlight channel name
            elif 'search_channel' == action:
                if idx is None:
                    continue
                channel = area.get_current_channel()
                self.print_infos('Search: '+channel)
                tabs.highlight(channel)

            elif 'medium_play' == action:
                sel = self.get_user_selection(idx, area)
                self.item_list.play(sel)

            elif 'medium_playadd' == action:
                sel = self.get_user_selection(idx, area)
                self.item_list.playadd(sel)

            elif 'medium_stop' == action:
                self.item_list.stop()

            elif 'medium_remove' == action:
                # TODO if is being played: self.item_list.stop()
                sel = self.get_user_selection(idx, area)
                media = self.item_list.remove(sel)
                tabs.update_areas('medium', 'removed', media)
                area.user_selection = deque()

            elif 'channel_filter' == action:
                tabs.filter_by_channels()

            elif 'category_filter' == action:
                sel = self.get_user_selection(idx, area)
                if isinstance(tabs.get_current_area(), MediumArea):
                    media = self.item_list.medium_idx_to_objects(sel)
                    channels = [medium['channel'] for medium in media]
                else:
                    channels = self.item_list.channel_ids_to_objects('ui', sel)

                if channels:
                    categories = set(channels[0]['categories'])
                    for c in channels[1:]:
                        categories &= set(c['categories'])
                    init = list_to_commastr(categories)
                else:
                    init = ''

                all_categories = self.item_list.channel_get_categories()
                completer = CommaListCompleter(all_categories)
                category_str = self.status_area.run_command(
                    'category filter: ', init=init, completer=completer)

                if category_str is None:
                    continue
                if not category_str:
                    categories = None
                else:
                    categories = commastr_to_list(category_str)

                tabs.filter_by_categories(categories=categories)

            elif 'medium_sort' == action:
                tabs.sort_switch()

            elif 'state_filter' == action:
                tabs.state_switch()

            elif action in ('medium_read', 'medium_skip'):
                if 'medium_skip' == action:
                    skip = True
                else:
                    skip = False

                sel = self.get_user_selection(idx, area)
                media = self.item_list.switch_read(sel, skip)
                tabs.update_areas('medium', 'modified', media)
                area.user_selection = deque()

            elif 'medium_update' == action:
                sel = self.get_user_selection(idx, area)
                media = self.item_list.update_media(sel)
                tabs.update_areas('medium', 'modified', media)
                area.user_selection = deque()

            elif 'medium_tag' == action:
                sel = self.get_user_selection(idx, area)
                media = self.item_list.medium_idx_to_objects(sel)

                # Shared tags
                shared_tags = set.intersection(
                    *[set(c['tags']) for c in media])

                text = 'Comma separated shared tags: '
                init = list_to_commastr(shared_tags)

                if init:
                    init += ', '

                all_tags = self.item_list.medium_get_tags()
                completer = CommaListCompleter(all_tags)
                tag_str = (
                    self.status_area.run_command(text, init=init,
                                                 completer=completer))
                if tag_str is None:
                    continue
                tags = set(commastr_to_list(tag_str))

                add_tags = tags-shared_tags
                remove_tags = shared_tags-tags

                media = self.item_list.medium_set_tags(
                    'ui', sel, add_tags, remove_tags)
                tabs.update_areas('medium', 'modified', media, only=True)

            elif 'tag_filter' == action:
                sel = self.get_user_selection(idx, area)
                media = self.item_list.medium_idx_to_objects(sel)

                if media:
                    tags = set(media[0]['tags'])
                    for c in media[1:]:
                        tags &= set(c['tags'])
                    init = list_to_commastr(tags)
                else:
                    init = ''

                all_tags = self.item_list.medium_get_tags()
                completer = CommaListCompleter(all_tags)
                tag_str = self.status_area.run_command(
                    'tag filter: ', init=init, completer=completer)

                if tag_str is None:
                    continue
                if not tag_str:
                    tags = None
                else:
                    tags = commastr_to_list(tag_str)

                tabs.filter_by_tags(tags=tags)

            elif 'medium_show_channel' == action:
                sel = self.get_user_selection(idx, area)
                media = self.item_list.medium_idx_to_objects(sel)
                if media:
                    ids = [m['channel']['id'] for m in media]
                    tabs.show_tab('channels')
                    tabs.filter_by_ids(list(set(ids)))

            ###################################################################
            # Remote medium commands
            ###################################################################
            elif 'medium_download' == action:
                sel = self.get_user_selection(idx, area)
                media = self.item_list.download(sel)
                tabs.update_areas('medium', 'modified', media)
                area.user_selection = deque()

            elif 'channel_update' == action:
                # If in channel tab we update only user_selection
                if 'channels' == area.key_class:
                    sel = self.get_user_selection(idx, area)
                # We update all channels
                else:
                    sel = None
                self.item_list.update_channels('ui', channel_ids=sel,
                                               cb=tabs.update_areas)

            ###################################################################
            # Local medium commands
            ###################################################################
            elif 'save_as_playlist' == action:
                sel = self.get_user_selection(idx, area)
                media = self.item_list.medium_idx_to_objects(sel)
                filenames = [m['filename'] for m in media]

                # Choose base name
                text = 'Playlist name: '
                destfile = self.status_area.run_command(text)
                if destfile is None:
                    continue
                destfile += '.m3u'

                try:
                    with open(destfile, 'w') as f:
                        for filename in filenames:
                            f.write(f'{filename}\n')
                except FileNotFoundError as e:
                    self.print_infos(e, mode='error')
                    continue

            ###################################################################
            # Downloading medium commands
            ###################################################################

            ###################################################################
            # Channel commands
            ###################################################################
            elif 'channel_auto' == action:
                sel = self.get_user_selection(idx, area)
                channels = self.item_list.channel_set_auto('ui', sel)
                tabs.update_areas('channel', 'modified', channels, only=True)

            elif 'channel_auto_custom' == action:
                sel = self.get_user_selection(idx, area)
                auto = self.status_area.run_command('auto: ')
                if auto is None:
                    continue
                channels = self.item_list.channel_set_auto('ui', sel, auto)
                tabs.update_areas('channel', 'modified', channels, only=True)

            elif 'channel_show_media' == action:
                sel = self.get_user_selection(idx, area)
                channels = [self.item_list.channels[s] for s in sel]
                if channels:
                    tabs.show_tab('remote')
                    tabs.filter_by_channels(channels)

            elif 'channel_category' == action:
                sel = self.get_user_selection(idx, area)
                channels = self.item_list.channel_ids_to_objects('ui', sel)

                # Shared categories
                shared_categories = set.intersection(
                    *[set(c['categories']) for c in channels])

                text = 'Comma separated shared categories: '
                init = list_to_commastr(shared_categories)

                if init:
                    init += ', '

                all_categories = self.item_list.channel_get_categories()
                completer = CommaListCompleter(all_categories)
                category_str = (
                    self.status_area.run_command(text, init=init,
                                                 completer=completer))
                if category_str is None:
                    continue
                categories = set(commastr_to_list(category_str))

                add_categories = categories-shared_categories
                remove_categories = shared_categories-categories

                channels = self.item_list.channel_set_categories(
                    'ui', sel, add_categories, remove_categories)
                tabs.update_areas('channel', 'modified', channels, only=True)

            elif 'channel_mask' == action:
                sel = self.get_user_selection(idx, area)
                channels = self.item_list.channel_ids_to_objects('ui', sel)
                if len(channels) != 1:
                    self.print_infos('Cannot change mask of several channels',
                                     mode='error')
                    continue

                channel = channels[0]
                text = 'Mask: '
                init = channel['mask']

                mask = self.status_area.run_command(text, init=init)
                if mask is None:
                    continue

                channel = self.item_list.channel_set_mask('ui', sel, mask)
                tabs.update_areas('channel', 'modified', [channel], only=True)

            # Action not recognized
            else:
                self.print_infos('Unknown action "%s"' % action, mode='error')

        self.item_list.player.stop()  # To prevent segfault in some cases
        curses.endwin()

    def get_user_selection(self, idx, area):
        if not area.user_selection:
            if idx is None or idx < 0:
                return []
            sel = [idx]
        else:
            sel = area.user_selection
        return sel

    def print_infos(self, *args, **kwargs):
        self.status_area.print(*args, **kwargs)

    def print_popup(self, string, position='bottom'):
        area = self.tabs.get_current_area()
        area.print_popup(string, position)

    def update_channels_task(self):
        while True:
            if self.update_minutes:
                if (time.time()-self.item_list.lastupdate >
                        self.update_minutes*60):
                    self.item_list.update_channels(
                        'ui', wait=True, cb=self.tabs.update_areas)

            # Check frequently in case update_minutes changes
            time.sleep(30)

    def refresh(self, reset=False):
        self.screen.clear()
        area = self.tabs.get_current_area()
        area.init_win()
        if reset:
            area.reset_contents()
        self.tabs.show_tab()
        self.status_area.init_win()

    def print_terminal(self, message, mutex=None):
        if not isinstance(message, str):
            message = '\n'.join(message)

        if mutex is not None:
            mutex.acquire()
        curses.endwin()
        screen_reset()
        print(message)
        input("-- Press Enter to continue --")
        screen = curses.initscr()
        self.screen = screen
        self.refresh()
        if mutex is not None:
            mutex.release()


class Tabs:
    def __init__(self, screen, item_list, print_infos):
        self.screen = screen
        self.item_list = item_list
        self.print_infos = print_infos
        self.current_idx = -1
        self.areas = []
        self.title_area = TitleArea(screen, '')

    def get_area_idx(self, name):
        for idx, area in enumerate(self.areas):
            if name == area.name:
                return idx
        return None

    def add_media(self, location, name):
        area = MediumArea(self.screen, location, self.item_list.media, name,
                          self.title_area, self.print_infos)
        self.areas.append(area)

    def add_channels(self, name, display_name):
        area = ChannelArea(self.screen, self.item_list.channels, name,
                           display_name, self.title_area, self.print_infos,
                           self.item_list.db)
        self.areas.append(area)

    def get_current_area(self):
        return self.get_area(self.current_idx)

    def get_area(self, idx):
        return self.areas[idx]

    # When target is None refresh current tab
    def show_tab(self, target=None):
        if target is not None:
            if isinstance(target, str):
                idx = self.get_area_idx(target)
            else:
                idx = target

            # Hide previous tab
            if -1 != self.current_idx:
                self.get_current_area().shown = False

            self.current_idx = idx
            area = self.get_area(idx)
        else:
            area = self.get_current_area()

        self.title_area = TitleArea(self.screen, area.get_title_name())
        area.display(True)

    def show_next_tab(self, reverse=False):
        if reverse:
            way = -1
        else:
            way = 1
        self.show_tab((self.current_idx+1*way) % len(self.areas))

    def move_screen(self, what, way):
        area = self.get_current_area()
        area.move_screen(what, way)

    def highlight(self, search_string):
        area = self.get_current_area()
        area.highlight(search_string)

    def filter_by_channels(self, channels=None):
        area = self.get_current_area()
        area.filter_by_channels(channels)

    def filter_by_categories(self, categories=None):
        area = self.get_current_area()
        area.filter_by_categories(categories)

    def filter_by_tags(self, tags=None):
        area = self.get_current_area()
        area.filter_by_tags(tags)

    def filter_by_ids(self, ids=None):
        area = self.get_current_area()
        area.filter_by_ids(ids)

    def filter_clear(self):
        area = self.get_current_area()
        area.filter_clear()

    def sort_switch(self):
        area = self.get_current_area()
        area.switch_sort()

    def state_switch(self):
        area = self.get_current_area()
        area.filter_next_state()

    def screen_infos(self):
        area = self.get_current_area()
        area.screen_infos()

    def next_highlight(self, reverse=False):
        area = self.get_current_area()
        area.next_highlight(reverse)

    def select_item(self):
        area = self.get_current_area()
        area.add_to_user_selection()

    def select_until(self):
        area = self.get_current_area()
        area.add_until_to_user_selection()

    def select_clear(self):
        area = self.get_current_area()
        area.clear_user_selection()

    def get_current_line(self):
        area = self.get_current_area()
        return area.get_current_line()

    def get_medium_areas(self):
        return [a for a in self.areas if isinstance(a, MediumArea)]

    def get_channel_areas(self):
        return [a for a in self.areas if isinstance(a, ChannelArea)]

    def update_areas(self, item_type, state, items=None, only=False):
        if items is None:
            for area in self.areas:
                area.reset_contents()

        else:
            if item_type == 'channel':
                self.update_channel_areas(items, state)
                if not only:
                    media = [m for c in items for m in c['media']]
                    self.update_medium_areas(media, state)
            elif item_type == 'medium':
                self.update_medium_areas(items, state)
                if not only:
                    # Channels without duplicates
                    channels = {m['channel']['id']: m['channel']
                                for m in items}.values()
                    self.update_channel_areas(channels, 'modified')
            else:
                raise(ValueError(f'Bad item_type ({item_type})'))

    def update_medium_areas(self, items, state):
        if state == 'new':
            for area in self.get_medium_areas():
                area.add_contents(items)

        elif state == 'modified':
            for area in self.get_medium_areas():
                area.update_contents(items)

        elif state == 'removed':
            for area in self.get_medium_areas():
                # TODO add remove_contents function
                area.reset_contents()

        else:
            raise(ValueError(f'Bad state ({state})'))

    def update_channel_areas(self, items, state):
        if state == 'new':
            for area in self.get_channel_areas():
                area.add_contents(items)

        elif state == 'modified':
            for area in self.get_channel_areas():
                area.update_contents(items)

        elif state == 'removed':
            for area in self.get_channel_areas():
                # TODO add remove_contents function
                area.reset_contents()

        else:
            raise(ValueError(f'Bad state ({state})'))


class ItemArea:
    def __init__(self, screen, items, name, display_name, title_area,
                 print_infos):
        self.print_infos = print_infos
        self.screen = screen
        self.title_area = title_area
        self.mutex = Lock()
        self.name = name
        self.display_name = display_name
        self.highlight_on = False
        self.highlight_string = None
        self.old_cursor = 0
        self.cursor = 0
        self.last_selected_idx = 0
        self.first_line = 0
        self.last_selected_item = None
        self.contents = None
        self.shown = False
        self.items = items
        self.selection = deque()
        self.user_selection = deque()
        self.sort = None

        self.init_win()
        self.add_contents()

    def init_win(self):
        height, width = self.screen.getmaxyx()
        self.height = height-2
        self.width = width-1
        self.win = curses.newwin(self.height+1, self.width, 1, 0)
        self.win.bkgd(curses.color_pair(2))

    def get_title_name(self):
        filters = [
            f'{k}: {list_to_commastr(self.filters[k])}'
            for k in self.filters
            if self.filters[k]
        ]
        if not filters:
            filters = ['All shown']
        return f'{self.display_name} - {"; ".join(filters)}'

    def add_to_user_selection(self, idx=None):
        if idx is None:
            idx = self.get_idx()

        try:
            self.user_selection.remove(idx)
        except ValueError:
            self.user_selection.append(idx)

    def add_until_to_user_selection(self):
        idx = self.get_idx()
        if idx is None:
            return

        start = self.selection.index(self.user_selection[-1])
        end = self.selection.index(idx)

        if start < end:
            step = 1
        else:
            step = -1

        for i in range(start, end, step):
            sel = self.selection[i+step]
            self.add_to_user_selection(sel)

        self.display(redraw=True)

    def clear_user_selection(self):
        self.user_selection = []
        self.display(redraw=True)

    def reset_contents(self):
        self.mutex.acquire()
        self.contents = None
        self.mutex.release()
        if self.shown:
            self.display(True)

    def add_contents(self, items=None):
        self.mutex.acquire()

        if self.contents is None:
            self.contents = deque()

        if items is None:
            items = self.items
            self.contents = deque()
            self.selection = deque()
            self.user_selection = deque()
        else:
            shift = len(items)
            self.selection = deque([s+shift for s in self.selection])
            self.user_selection = deque([s+shift for s in self.user_selection])

        items = self.filter(items)[0]
        self.selection.extendleft([item['index'] for item in items])
        self.contents.extendleft(self.items_to_string(items))

        self.mutex.release()

        if self.shown:
            self.display(True)

    def update_contents(self, items):
        if self.contents is None:
            items = self.items

        # We keep only items already in item_list
        items = [i for i in items if 'index' in i]

        # Check if item is kept or not
        shown_items, hidden_items = self.filter(items)

        self.mutex.acquire()

        if self.contents is None:
            self.contents = deque()

        for item in shown_items:
            try:
                idx = self.selection.index(item['index'])
            except ValueError:  # if item not in selection
                # We need to show it: update contents and selection
                position = bisect(self.selection, item['index'])
                self.contents.insert(position, self.item_to_string(item))
                self.selection.insert(position, item['index'])
            else:  # if item in selection
                # Update shown information
                self.contents[idx] = self.item_to_string(item)

        for item in hidden_items:
            try:
                idx = self.selection.index(item['index'])
            except ValueError:  # if item not in selection
                pass  # Noting to do
            else:  # if item in selection
                # Hide it: update contents and selection
                del self.contents[idx]
                del self.selection[idx]

        self.mutex.release()

        if self.shown:
            self.display(True)  # TODO depending on changes

    def sort_selection(self, col):
        idtt = range(len(self.selection))
        if col is None:
            permutation = sorted(idtt, key=lambda i: self.contents[i],
                                 reverse=True)
        else:
            permutation = sorted(
                idtt, key=lambda i: self.items[self.selection[i]][col])

        self.selection = deque([self.selection[p] for p in permutation])
        self.contents = deque([self.contents[p] for p in permutation])

    def switch_sort(self):
        if self.sort is None:
            self.sort = 'duration'
        else:
            self.sort = None

        self.sort_selection(self.sort)
        self.display(True)

    def items_to_string(self, items):
        return list(map(lambda x: self.item_to_string(x), items))

    def screen_infos(self):
        line = self.first_line+self.cursor+1
        total = len(self.selection)
        self.print_infos('%d/%d' % (line, total))

    def get_idx(self):
        if self.selection:
            return self.selection[self.first_line+self.cursor]
        else:
            return None

    def get_current_item(self):
        if self.get_idx() is None:
            return None
        return self.items[self.get_idx()]

    def get_current_line(self):
        if self.first_line+self.cursor < 0:
            return ''
        return self.contents[self.first_line+self.cursor]

    def highlight(self, string):
        if not string:
            return
        self.highlight_on = True
        self.highlight_string = string
        self.display(redraw=True)
        self.next_highlight()

    def next_highlight(self, reverse=False):
        if self.highlight_string is None:
            return

        item_idx = None
        no_case_string = self.highlight_string.casefold()
        if not reverse:
            for i in range(self.first_line+self.cursor+1, len(self.contents)):
                if no_case_string in self.contents[i].casefold():
                    item_idx = i
                    break
        else:
            for i in range(self.first_line+self.cursor-1, -1, -1):
                if no_case_string in self.contents[i].casefold():
                    item_idx = i
                    break

        if item_idx is not None:
            self.move_cursor(item_idx)

    def no_highlight(self):
        self.highlight_on = False
        self.display(redraw=True)

    def move_cursor(self, item_idx):
        self.move_screen('line', 'down', item_idx-self.cursor-self.first_line)

    def print_line(self, line, string, style=None):
        normal_style = curses.color_pair(2)
        bold_style = curses.color_pair(1)
        select_style = curses.color_pair(2) | curses.A_REVERSE
        highlight_style = curses.color_pair(3)
        greyedout_style = curses.color_pair(4)

        # Style can be embedded in string with :<b,g>:
        if len(string) > 3 and string[0] == ':' and string[2] == ':':
            if style is not None:
                pass
            elif string[1] == 'b':
                style = 'bold'
            elif string[1] == 'g':
                style = 'greyedout'
            string = string[3:]

        try:
            self.win.move(line, 0)
            self.win.clrtoeol()

            if not string:
                self.win.refresh()
                return

            if style == 'bold':
                self.win.addstr(line, 0, string, bold_style)
            else:
                # If line is in user selection
                if self.selection[line+self.first_line] in self.user_selection:
                    self.win.addstr(line, 0, string, select_style)

                elif self.highlight_on:
                    styles = (normal_style, highlight_style)

                    # Split with highlight string and put it back
                    parts = re.split('('+self.highlight_string+')',
                                     string, flags=re.IGNORECASE)

                    written = 0
                    style_idx = 0
                    for part in parts:
                        self.win.addstr(line, written, part, styles[style_idx])
                        written += len(part)
                        style_idx = (style_idx+1) % 2
                elif style == 'greyedout':
                    self.win.addstr(line, 0, string, greyedout_style)
                else:
                    self.win.addstr(line, 0, string, normal_style)

            self.win.refresh()
        except curses.error:
            pass

    def show_help(self, keymap):
        lines = []
        lines.append('In main area')
        lines.append('============')
        lines.extend(keymap.map_to_help(self.key_class))

        lines.append('')
        lines.append("In mpv (launched from termipod")
        lines.append("==============================")
        lines.append("?      Show new commands")

        lines.append('')
        lines.append("In command line")
        lines.append("===============")
        lines.append("^L      Redraw line")
        lines.append("^U      Clear line")

        self.print_popup(lines, 'cursor')

    def show_command_help(self, cmd=None, error=False):
        if error:
            if cmd is not None:
                self.print_infos(f'Invalid syntax for {cmd}!', mode='error')
            else:
                self.print_infos('Invalid syntax!', mode='error')

        # TODO commands as parameter (dynamic depending in area)
        commands = {
            'add': (
                'Add channel',
                'add <url> [count=<max items>] [strict[=<0 or 1>]] '
                '[auto[=<regex>]] [mask=<regex>] '
                '[categories=<category1,category2>] '
                '[force[=<0|1]> [name=<new name>]'
            ),
            'addvideo': (
                'Add video (in disabled channel)',
                'add <url> [categories=<category1,category2>] '
                '[force[=<0|1]> [name=<new name>]'
            ),
            'messages': (
                'Print last messages',
                'messages [outputfile]'
            ),
            'errors': (
                'Print last errors',
                'errors [outputfile]'
            ),
            'channelDisable': (
                'Disable selected channels',
                'channelDisable'),
            'channelEnable': (
                'Enable selected channels',
                'channelEnable'),
            'channelRemove': (
                'Remove selected channels (and all associated media)',
                'channelRemove'
            ),
            'httpServerStart': (
                'Start local file streaming server',
                'httpServerStart'
            ),
            'httpsErverStop': (
                'Stop streaming server',
                'httpserverStop'
            ),
            'httpServerStatus': (
                'Get streaming server status',
                'httpServerStatus'
            ),
            'quit': (
                'Quit',
                'q[uit]'
            ),
        }

        lines = []
        if cmd is None:
            for key, desc in commands.items():
                lines.append(f'{key} - {desc[0]}')
                lines.append(f'  Usage: {desc[1]}')
        else:
            desc = commands[cmd]
            lines.append(f'{cmd} - {desc[0]}')
            lines.append(f'  Usage: {desc[1]}')

        self.print_popup(lines, 'bottom')

    def print_popup(self, raw_lines, position, margin=5, sticky=False):
        if position == 'cursor':
            base = self.cursor
        elif position == 'bottom':
            base = self.height
        else:
            raise(ValueError('Bad position'))

        outer_margin = margin
        inner_margin = 2
        width = self.width-outer_margin*2
        text_width = width-inner_margin*2

        lines = []
        for l in raw_lines:
            lines.extend(format_string(l, text_width, truncate=False))

        height = len(lines)+2  # for border

        # Compute first line position
        if height > self.height:
            lines = lines[:self.height-2]
            lines[-1] = lines[-1][:-1]+'…'
            self.print_infos('Truncated, too many lines!')
            height = len(lines)+2

        start = max(1, base-int(len(lines)/2))
        if start+height-1 > self.height:
            start = max(1, self.height+1-height)

        win = curses.newwin(height, width, start, outer_margin)
        win.bkgd(curses.color_pair(2) | curses.A_REVERSE)
        win.keypad(1)
        win.border('|', '|', '-', '-', '+', '+', '+', '+')

        try:
            for line in range(len(lines)):
                win.move(line+1, inner_margin)
                win.addstr(line+1, inner_margin, str(lines[line]))
            win.refresh()
        except curses.error:
            pass

        keymap = get_keymap()
        this_popup_key = get_last_key()
        move_keys = {
            get_key_code(k)
            for a in [
                'line_down',
                'line_up',
                'page_down',
                'page_up',
                'top',
                'bottom',
                'search_next',
                'search_prev',
            ]
            for k in keymap.get_keys(a)
        }

        key = get_key(self.screen)

        if sticky:
            if key == this_popup_key:
                pass
            elif key not in move_keys:
                curses.ungetch(key)
            else:
                curses.ungetch(this_popup_key)
                curses.ungetch(key)
        else:
            curses.ungetch(key)

        self.display(redraw=True)

    def show_infos(self):
        item = self.get_current_item()
        if item is None:
            return

        lines = self.item_to_string(item, multi_lines=True)

        self.print_popup(lines, 'cursor', sticky=True)

    def show_description(self):
        item = self.get_current_item()
        lines = item['description'].split('\n')

        self.print_popup(lines, 'cursor', sticky=True)

    def position_to_idx(self, first_line, cursor):
        return first_line+cursor

    def idx_to_position(self, idx):
        first_line = int(idx/self.height)*self.height
        cursor = idx-first_line
        return (first_line, cursor)

    def move_screen(self, what, way, number=1):
        redraw = False
        # Move one line down
        idx = self.position_to_idx(self.first_line, self.cursor)
        if what == 'line' and way == 'down':
            # More lines below
            idx += number
        # Move one line up
        elif what == 'line' and way == 'up':
            # More lines above
            idx -= number
        # Move one page down
        elif what == 'page' and way == 'down':
            idx += self.height*number
        # Move one page up
        elif what == 'page' and way == 'up':
            idx -= self.height*number
        elif what == 'all' and way == 'up':
            idx = 0
        elif what == 'all' and way == 'down':
            idx = len(self.contents)-1

        if 0 > idx:
            idx = 0
        elif len(self.contents) <= idx:
            idx = len(self.contents)-1

        first_line, cursor = self.idx_to_position(idx)

        # If first line is not the same: we redraw everything
        if (first_line != self.first_line):
            redraw = True

        self.old_cursor = self.cursor
        self.cursor = cursor
        self.first_line = first_line

        self.last_selected_idx = idx
        if self.selection:  # if display is not empty
            self.last_selected_item = self.items[self.selection[idx]]
        self.display(redraw)

    def reset_display(self):
        self.old_cursor = 0
        self.cursor = 0
        self.first_line = 0
        self.last_selected_idx = 0
        self.display(True)

    def display(self, redraw=False):
        self.shown = True

        if self.contents is None:
            redraw = True
            self.add_contents()
            self.title_area.print(self.get_title_name())
            return

        self.mutex.acquire()

        if self.contents and redraw:
            if self.last_selected_item is not None:
                # Set cursor on the same item than before redisplay
                try:
                    global_idx = self.last_selected_item['index']
                    idx = self.selection.index(global_idx)

                # Previous item is not shown anymore
                except ValueError:
                    idx = min(len(self.selection)-1, self.last_selected_idx)
                    self.last_selected_idx = idx
                self.first_line, self.cursor = self.idx_to_position(idx)
                self.last_selected_item = self.items[self.selection[idx]]
                redraw = True

            else:
                self.first_line, self.cursor = (0, 0)
                self.last_selected_item = self.items[self.selection[0]]

        # Check cursor position
        idx = self.position_to_idx(self.first_line, self.cursor)
        if len(self.contents) <= idx:
            idx = len(self.contents)-1
            self.first_line, self.cursor = self.idx_to_position(idx)

        # We draw all the page (shift)
        if redraw:
            for line_number in range(self.height):
                if self.first_line+line_number < len(self.contents):
                    line = self.contents[self.first_line+line_number]
                    # Line where cursor is, bold
                    if line_number == self.cursor:
                        self.print_line(line_number, line, style='bold')
                    else:
                        self.print_line(line_number, line)

                # Erase previous text for empty lines (bottom of scroll)
                else:
                    self.print_line(line_number, '')

        elif self.old_cursor != self.cursor:
            self.print_line(self.old_cursor,
                            self.contents[self.first_line+self.old_cursor])
            self.print_line(self.cursor,
                            self.contents[self.first_line+self.cursor],
                            style='bold')

        self.mutex.release()

    def get_key_class(self):
        return self.key_class

    def filter_clear(self):
        for k in self.filters:
            self.filters[k] = None

        # Update screen
        self.reset_contents()


class MediumArea(ItemArea):
    def __init__(self, screen, location, items, name, title_area, print_infos):
        self.location = location
        self.key_class = 'media_'+location
        self.filters = {
            'state': 'unread',
            'channels': None,
            'categories': None,
            'tags': None,
        }

        super().__init__(screen, items, location, name, title_area,
                         print_infos)

    def extract_channel_name(self, line):
        parts = line.split(u" \u2022 ")
        if len(parts) >= 2:
            return line.split(u" \u2022 ")[1]
        return ''

    def get_current_channel(self):
        line = self.get_current_line()
        return self.extract_channel_name(line)

    def filter_by_channels(self, channels=None):
        if channels is None and self.filters['channels']:
            self.filters['channels'] = None
        else:
            if channels is None:
                if not self.user_selection:
                    medium = self.get_current_item()
                    channel_titles = [medium['channel']['title']]

                else:
                    media = [self.items[i] for i in self.user_selection]
                    channel_titles = [m['channel']['title'] for m in media]

                self.filters['channels'] = list(set(channel_titles))

            else:
                self.filters['channels'] = list(
                    set([c['title'] for c in channels]))

        # Update screen
        self.reset_contents()

    def filter_by_categories(self, categories=None):
        if categories is None and self.filters['categories']:
            self.filters['categories'] = None
        else:
            if categories is None:
                if not self.user_selection:
                    medium = self.get_current_item()
                    channel_categories = medium['channel']['categories']

                else:
                    media = [self.items[i] for i in self.user_selection]
                    channel_categories = [m['channel']['categories']
                                          for m in media]

                self.filters['categories'] = list(set(channel_categories))

            else:
                self.filters['categories'] = categories

        # Update screen
        self.reset_contents()

    def filter_by_tags(self, tags=None):
        if tags is None and self.filters['tags']:
            self.filters['tags'] = None
        else:
            if tags is None:
                if not self.user_selection:
                    medium = self.get_current_item()
                    medium_tags = medium['tags']

                else:
                    media = [self.items[i] for i in self.user_selection]
                    medium_tags = [m['tags'] for m in media]

                self.filters['tags'] = list(set(medium_tags))

            else:
                self.filters['tags'] = tags

        # Update screen
        self.reset_contents()

    def filter_next_state(self):
        states = ['all', 'unread', 'read', 'skipped']
        idx = states.index(self.filters['state'])
        self.filters['state'] = states[(idx+1) % len(states)]
        self.print_infos('Show %s media' % self.filters['state'])
        self.reset_contents()

    # if new_items update selection (do not replace)
    def filter(self, new_items):
        matching_items = []
        other_items = []
        for item in new_items:
            match = True
            if self.location != item['location']:
                match = False

            elif ('all' != self.filters['state']
                  and self.filters['state'] != item['state']):
                match = False

            elif (self.filters['channels'] is not None
                    and item['channel']['title']
                    not in self.filters['channels']):
                match = False

            elif (self.filters['categories'] is not None
                  and (set(self.filters['categories'])
                       - set(item['channel']['categories']))):
                match = False

            elif (self.filters['tags'] is not None
                  and (set(self.filters['tags'])
                       - set(item['tags']))):
                match = False

            if match:
                matching_items.append(item)
            else:
                other_items.append(item)

        return (matching_items, other_items)

    def item_to_string(self, medium, multi_lines=False, width=None):
        if width is None:
            width = self.width

        formatted_item = dict(medium)
        formatted_item['date'] = ts_to_date(medium['date'])
        formatted_item['duration'] = duration_to_str(medium['duration'])
        formatted_item['channel'] = formatted_item['channel']['title']
        formatted_item['tags'] = list_to_commastr(medium['tags'])
        try:
            formatted_item['size'] = (
                str(int(os.path.getsize(
                    formatted_item['filename'])/1024**2))+'MB'
                if formatted_item['filename']
                else '')
        except FileNotFoundError:
            formatted_item['size'] = ''

        separator = u" \u2022 "

        if not multi_lines:
            string = formatted_item['date']
            string += separator
            string += formatted_item['channel']
            string += separator
            string += formatted_item['title']

            string = format_string(
                string,
                width-len(separator+formatted_item['duration']))
            string += separator
            string += formatted_item['duration']

        else:
            fields = ['title', 'channel', 'date', 'duration', 'tags',
                      'filename', 'size', 'link']
            string = []
            for f in fields:
                s = '%s%s: %s' % (separator, f, formatted_item[f])
                string.append(s)

        return string


class ChannelArea(ItemArea):
    def __init__(self, screen, items, name, display_name, title_area,
                 print_infos, data_base):
        self.key_class = 'channels'
        self.data_base = data_base
        self.filters = {
            'ids': None,
            'categories': None,
        }

        super().__init__(screen, items, name, display_name, title_area,
                         print_infos)

    def filter(self, new_items):
        matching_items = []
        other_items = []
        for item in new_items:
            match = True
            if (self.filters['categories'] is not None
                    and (set(self.filters['categories'])
                         - set(item['categories']))):
                match = False

            elif (self.filters['ids'] is not None
                  and item['id'] not in self.filters['ids']):
                match = False

            if match:
                matching_items.append(item)
            else:
                other_items.append(item)

        return (matching_items, other_items)

    def filter_by_categories(self, categories=None):
        if categories is None and self.filters['categories']:
            self.filters['categories'] = None
        else:
            if categories is None:
                if not self.user_selection:
                    channel = self.get_current_item()
                    channel_categories = channel['categories']

                else:
                    channels = [self.items[i] for i in self.user_selection]
                    channel_categories = [c['categories'] for c in channels]

                self.filters['categories'] = list(set(channel_categories))

            else:
                self.filters['categories'] = categories

        # Update screen
        self.reset_contents()

    def filter_by_ids(self, ids=None):
        if ids is None and self.filters['ids']:
            self.filters['ids'] = None
        else:
            self.filters['ids'] = ids

        # Update screen
        self.reset_contents()

    def item_to_string(self, channel, multi_lines=False, width=None):
        nunread_elements = len([m for m in channel['media']
                               if m['state'] == 'unread'])
        ntotal_elements = len(channel['media'])

        updated_date = ts_to_date(channel['updated'])
        try:
            last_medium_date = ts_to_date(channel['media'][-1]['date'])
        except IndexError:
            last_medium_date = ts_to_date(0)

        separator = u" \u2022 "

        if not multi_lines:
            # TODO format and align
            string = ':g:' if channel['disabled'] else ''
            string += channel['title']
            string += separator
            string += channel['type']
            string += separator
            string += f'{nunread_elements}/{ntotal_elements}'
            string += separator
            string += list_to_commastr(channel['categories'])
            string += separator
            string += channel['auto']
            string += separator
            string += f'{last_medium_date} ({updated_date})'

        else:
            formatted_item = dict(channel)
            formatted_item['updated'] = updated_date
            formatted_item['unread'] = nunread_elements
            formatted_item['total'] = ntotal_elements
            formatted_item['categories'] = (
                list_to_commastr(formatted_item['categories']))
            if channel['addcount'] == -1:
                formatted_item['added items at creation'] = 'all'
            else:
                formatted_item['added items at creation'] = (
                    f'{channel["addcount"]} (incomplete)')
            fields = ['title', 'type', 'updated', 'url', 'categories',
                      'auto', 'mask', 'added items at creation', 'unread',
                      'total']
            string = []
            for f in fields:
                s = '%s%s: %s' % (separator, f, formatted_item[f])
                string.append(s)

        return string


class TitleArea:
    def __init__(self, screen, title):
        self.screen = screen
        self.title = title
        self.init_win()

    def init_win(self):
        height, width = self.screen.getmaxyx()
        self.height = 1
        self.width = width-1
        self.win = curses.newwin(self.height, self.width, 0, 0)
        self.win.bkgd(curses.color_pair(2) | curses.A_REVERSE)
        self.win.keypad(1)

        self.print(format_string(self.title, self.width-1))
        # self.print(self.title)

    def print(self, string):
        try:
            self.win.move(0, 0)
            self.win.clrtoeol()
            self.win.addstr(0, 0, str(string))
            self.win.refresh()
        except curses.error:
            pass


class StatusArea:
    def __init__(self, screen, print_popup, print_terminal):
        self.screen = screen
        self.print_popup = print_popup
        self.print_terminal = print_terminal

        self.mutex = Lock()
        self.messages = Queue()
        self.max_messages = 5000
        self.errors = deque(maxlen=self.max_messages)
        self.all_messages = deque(maxlen=self.max_messages)
        self.need_to_wait = False
        message_handler = Thread(target=self.handle_queue)
        message_handler.daemon = True
        message_handler.start()

        self.init_win()

    def init_win(self):
        height, width = self.screen.getmaxyx()
        self.height = 1
        self.width = width-1
        self.win = curses.newwin(self.height, self.width, height-1, 0)
        self.win.bkgd(curses.color_pair(2) | curses.A_REVERSE)
        self.win.keypad(1)
        self.print('')

    def handle_queue(self):
        """This is the worker thread function. It processes items in the queue one
        after another.  These daemon threads go into an infinite loop, and only
        exit when the main thread ends."""
        while True:
            message = self.messages.get()
            self.print_raw_task(message)
            self.messages.task_done()
            sleep(.1)

    def print_raw_task(self, string, mutex=True, need_to_wait=False):
        self.all_messages.append(string)
        try:
            if mutex:
                self.mutex.acquire()

            # If error happened wait before showing new message
            if self.need_to_wait:
                wait_time = 1-(time.time()-self.need_to_wait)
                self.need_to_wait = 0
                if wait_time > 0:
                    sleep(wait_time)

            if need_to_wait:
                self.need_to_wait = time.time()

            self.win.move(0, 0)
            self.win.clrtoeol()
            self.win.addstr(0, 0, str(string))
            self.win.refresh()
        except curses.error:
            pass
        finally:
            if mutex:
                self.mutex.release()

    def print_raw(self, string, mutex=True, need_to_wait=False):
        print_handler = Thread(target=self.print_raw_task,
                               args=(string, ),
                               kwargs={'mutex': mutex,
                                       'need_to_wait': need_to_wait})
        print_handler.daemon = True
        print_handler.start()

    def print(self, value, mode=None, mutex=True):
        if mode not in (None, 'direct', 'error', 'prompt'):
            raise ValueError('Wrong print mode')

        string = str(value)
        print_log(string)

        string = printable_str(string)

        if len(string)+1 > self.width:
            short_string = string[:self.width-4]+'.'*3
        else:
            short_string = string

        if mode in ('direct', 'error', 'prompt'):
            if mode == 'prompt':
                need_to_wait = False
            else:
                need_to_wait = True
            self.print_raw(short_string, mutex=mutex,
                           need_to_wait=need_to_wait)
        else:
            self.messages.put(short_string)

        if mode == 'error':
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.errors.append(f'[{now}] {string}')

    def print_errors(self, file=None):
        self.print_messages(self.errors, file)

    def print_all_messages(self, file=None):
        self.print_messages(self.all_messages, file)

    def print_messages(self, messages, file=None):
        if file is not None:
            with open(file, 'w') as f:
                print('\n'.join(messages), f)
        else:
            self.print_terminal(messages, mutex=self.mutex)

    def run_command(self, prefix, init='', completer=None):
        with Textbox(self.win, self.mutex, self.print, self.print_popup,
                     self.print_terminal) as tb:
            return tb.run(prefix, init, completer)


class Textbox:
    def __init__(self, win, mutex, printf, popupf, terminalf):
        self.win = win
        self.mutex = mutex
        self.print = printf
        self.popup = popupf
        self.terminal = terminalf
        self.completion = False
        self.mutex.acquire()

    def __enter__(self):
        return self

    def __del__(self):
        self.mutex.release()

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    def run(self, prefix, init, completer):
        self.prefix = prefix
        self.win.move(0, 0)
        self.print(self.prefix+init, mode='prompt', mutex=False)
        y, x = self.win.getyx()
        self.start = x-len(init)

        curses.curs_set(1)  # enable cursor
        tb = curses.textpad.Textbox(self.win, insert_mode=True)
        tb.stripspaces = False

        self.completer = completer
        string = tb.edit(self.handle_key)

        if string.startswith(self.prefix):
            string = string[len(self.prefix):]  # remove prefix
            string = string.strip()  # remove last char
            ret = string

        else:  # If was cancelled by pressing escape key
            ret = None

        curses.curs_set(0)  # disable cursor
        return ret

    def handle_key(self, key):
        start = self.start

        if get_key_name(key) == '^?':
            y, x = self.win.getyx()
            if x == start:
                return None
            key = curses.KEY_BACKSPACE

        # Tab or Shitf-Tab
        elif get_key_name(key) == '\t' or get_key_name(key) == 'KEY_BTAB':
            if self.completer is None:
                return None

            if get_key_name(key) == '\t':
                way = 1
            else:
                way = -1

            # First tab press
            if not self.completion:
                y, x = self.win.getyx()
                inputstr = self.win.instr(y, 0, x).decode('utf8')
                self.win.move(y, x)

                inputstr = inputstr[len(self.prefix):]

                completions = self.completer.complete(inputstr)
                self.lastword = completions['replaced_token']
                self.compls = completions['candidates']
                self.desc = completions['helplines']

                self.userlastword = self.lastword
                self.complidx = -1
                # If only one result (not empty) force completion
                if len(self.compls) == 1:
                    self.completion = True
                else:
                    if not self.desc:
                        self.desc = ['Nothing to complete!']
                    self.popup(self.desc)

            # Direct next tab press
            if self.completion and self.compls:
                y, x = self.win.getyx()

                self.complidx += way
                if self.complidx == len(self.compls):
                    self.complidx = -1
                elif self.complidx == -2:
                    self.complidx = len(self.compls)-1

                if self.complidx == -1:
                    compl = self.userlastword
                else:
                    compl = self.compls[self.complidx]
                    if len(compl) <= len(self.userlastword):
                        compl = self.userlastword
                        self.complidx = -1

                try:
                    self.win.addstr(y, x-len(self.lastword), compl)
                    self.win.clrtoeol()
                    self.win.refresh()
                    self.lastword = compl
                except curses.error:
                    pass

                lines = [v if i != self.complidx else '> '+v
                         for i, v in enumerate(self.desc)]
                self.popup(lines)

            if self.completion and not self.compls:
                self.popup(self.desc)

            self.completion = True
            return None

        elif get_key_name(key) == '^L':
            y, x = self.win.getyx()
            inputstr = self.win.instr(y, 0, x).decode('utf8')
            self.win.clear()
            self.win.refresh()
            self.win.addstr(0, 0, inputstr)
            self.win.refresh()
            return None

        elif get_key_name(key) == '^U':
            self.win.move(0, 0)
            self.win.clrtoeol()
            self.win.addstr(0, 0, str(self.prefix))
            self.win.refresh()
            return None

        elif get_key_name(key) == '^[':
            y, x = self.win.getyx()
            self.win.move(y, 0)
            self.win.clrtoeol()
            self.win.refresh()
            # Return Ctrl-g to confirm
            return get_key_code('^G')

        self.completion = False
        self.complidx = -1
        return key
