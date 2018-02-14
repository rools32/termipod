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
import curses
import curses.textpad
import shlex
from bisect import bisect
from threading import Lock

from termipod.utils import duration_to_str, ts_to_date, print_log, \
                           format_string
from termipod.itemlist import ItemList
from termipod.keymap import Keymap, get_key_name


class UI():
    def __init__(self, config):
        screen = curses.initscr()
        screen.keypad(1)  # to handle special keys as one key
        height, width = screen.getmaxyx()
        screen.immedok(True)
        curses.start_color()
        curses.curs_set(0)  # disable cursor
        curses.cbreak()  # no need to press enter to react to keys
        curses.noecho()  # do not show pressed keys
        curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_BLACK, curses.COLOR_WHITE)
        curses.init_pair(4, curses.COLOR_RED, curses.COLOR_BLACK)
        screen.refresh()

        self.keymap = Keymap(config)

        self.status_area = StatusArea(screen)
        self.item_list = ItemList(config, self.print_infos)

        tabs = Tabs(screen, self.item_list, self.print_infos)

        # New tabs
        tabs.add_media('remote', 'Remote media')
        tabs.add_media('local', 'Playlist')
        tabs.add_media('download', 'Downloading')
        tabs.add_channels('channels', 'Channels')
        tabs.show_tab(0)

        while True:
            # Wait for key
            key_name = get_key_name(screen)
            area = tabs.get_current_area()

            area_key_class = area.get_key_class()
            idx = area.get_idx()

            action = self.keymap.get_action(area_key_class, key_name)
            print_log(action)

            if action is None:
                self.print_infos('Key %r not mapped for %s' %
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

            elif 'redraw' == action:
                tabs.show_tab()
                self.status_area.print('')

            elif 'refresh' == action:
                area.reset_contents()
                tabs.show_tab()
                self.status_area.print('')

            elif 'infos' == action:
                area.show_infos()

            elif 'description' == action:
                area.show_description()

            elif 'command_get' == action:
                string = self.status_area.run_command(':')
                command = shlex.split(string)

                if not command:
                    self.print_infos('No command to run')
                    continue

                self.print_infos('Run: '+str(command))
                if command[0] in ('q', 'quit'):
                    exit()
                elif command[0] in ('h', 'help'):
                    area.show_help(self.keymap)
                elif command[0] in ('add',):
                    if 1 == command:
                        add_help = 'Usage: add url [auto] [genre]'
                        self.print_infos(add_help)
                    else:
                        self.item_list.new_channel(*command[1:])
                else:
                    self.print_infos('Command "%s" not found' % command[0])

            elif 'search_get' == action:
                search_string = self.status_area.run_command('/')
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

            ###################################################################
            # Allmedia commands
            ###################################################################
            # Highlight channel name
            elif 'search_channel' == action:
                channel = area.get_current_channel()
                self.print_infos('Search: '+channel)
                tabs.highlight(channel)

            elif 'medium_play' == action:
                self.item_list.play(idx)

            elif 'medium_playadd' == action:
                self.item_list.playadd(idx)

            elif 'medium_stop' == action:
                self.item_list.stop()

            elif 'medium_remove' == action:
                # TODO if is being played: self.item_list.stop()
                self.item_list.remove(idx)

            elif 'channel_filter' == action:
                tabs.channel_filter_switch()

            elif 'state_filter' == action:
                tabs.state_switch()

            elif action in ('medium_read', 'medium_skip'):
                if 'medium_skip' == action:
                    skip = True
                else:
                    skip = False
                if not area.user_selection:
                    self.item_list.switch_read([idx], skip)
                else:
                    self.item_list.switch_read(area.user_selection, skip)
                    area.user_selection = []

            ###################################################################
            # Remote medium commands
            ###################################################################
            elif 'medium_download' == action:
                if not area.user_selection:
                    self.item_list.download([idx])
                else:
                    self.item_list.download(area.user_selection)
                    area.user_selection = []

            elif 'medium_update' == action:
                updated = self.item_list.update_medium_list()

            ###################################################################
            # Local medium commands
            ###################################################################

            ###################################################################
            # Downloading medium commands
            ###################################################################

            ###################################################################
            # Channel commands
            ###################################################################
            elif 'channel_auto' == action:
                self.item_list.channel_auto(idx)

            elif 'channel_auto_custom' == action:
                auto = self.status_area.run_command('auto: ')
                self.item_list.channel_auto(idx, auto)

            elif 'channel_show_media' == action:
                channel = self.item_list.channels[idx]
                self.item_list.channel_auto(idx)
                tabs.show_tab('remote')
                tabs.channel_filter_switch(channel['title'])

            else:
                self.print_infos('Unknown action "%s"' % action)

    def print_infos(self, string):
        self.status_area.print(string)


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
        self.item_list.add_medium_area(area)

    def add_channels(self, name, display_name):
        area = ChannelArea(self.screen, self.item_list.channels, name,
                           display_name, self.title_area, self.print_infos,
                           self.item_list.db)
        self.areas.append(area)
        self.item_list.add_channel_area(area)

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

    def channel_filter_switch(self, channel=None):
        area = self.get_current_area()
        area.channel_filter_switch(channel)

    def state_switch(self):
        area = self.get_current_area()
        area.switch_state()

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


class ItemArea:
    def __init__(self, screen, items, name, display_name, title_area,
                 print_infos):
        self.print_infos = print_infos
        self.screen = screen
        self.title_area = title_area
        self.mutex = Lock()
        height, width = screen.getmaxyx()
        self.height = height-2
        self.width = width-1
        self.name = name
        self.display_name = display_name
        self.win = curses.newwin(self.height+1, self.width, 1, 0)
        self.win.bkgd(curses.color_pair(2))
        self.highlight_on = False
        self.highlight_string = None
        self.old_cursor = 0
        self.cursor = 0
        self.first_line = 0
        self.last_selected_item = None
        self.contents = None
        self.shown = False
        self.items = items
        self.selection = []
        self.user_selection = []

        self.add_contents()

    def add_to_user_selection(self, idx=None):
        if idx is None:
            idx = self.get_idx()

        if idx in self.user_selection:
            self.user_selection.remove(idx)
        else:
            self.user_selection.append(idx)

    def add_until_to_user_selection(self):
        idx = self.get_idx()
        if idx < self.user_selection[-1]:
            step = -1
        else:
            step = 1

        start = self.selection.index(self.user_selection[-1])
        end = self.selection.index(idx)

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
            self.contents = []

        if items is None:
            items = self.items
            self.contents = []
            self.selection = []
            self.user_selection = []
        else:
            shift = len(items)
            self.selection = [s+shift for s in self.selection]
            self.user_selection = [s+shift for s in self.user_selection]

        items = self.filter(items)[0]
        self.selection[0:0] = [item['index'] for item in items]
        self.contents[0:0] = self.items_to_string(items)

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
            self.contents = []
            replace = True
        else:
            replace = False

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
        return self.items[self.get_idx()]

    def get_current_line(self):
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
        if not reverse:
            for i in range(self.first_line+self.cursor+1, len(self.contents)):
                if self.highlight_string in self.contents[i]:
                    item_idx = i
                    break
        else:
            for i in range(self.first_line+self.cursor-1, -1, -1):
                if self.highlight_string in self.contents[i]:
                    item_idx = i
                    break

        if item_idx is not None:
            self.move_cursor(item_idx)

    def no_highlight(self):
        self.highlight_on = False
        self.display(redraw=True)

    def move_cursor(self, item_idx):
        self.move_screen('line', 'down', item_idx-self.cursor-self.first_line)

    def print_line(self, line, string, bold=False):
        normal_style = curses.color_pair(2)
        bold_style = curses.color_pair(1)
        select_style = curses.color_pair(3)
        highlight_style = curses.color_pair(4)
        self.win.move(line, 0)
        self.win.clrtoeol()

        if not string:
            self.win.refresh()
            return

        style = None
        if bold:
            self.win.addstr(line, 0, string, bold_style)
        else:
            # If line is in user selection
            if self.selection[line+self.first_line] in self.user_selection:
                self.win.addstr(line, 0, string, select_style)

            elif self.highlight_on:
                styles = (normal_style, highlight_style)

                # Split with highlight string and put it back
                parts = string.split(self.highlight_string)
                missing_strings = [self.highlight_string]*len(parts)
                parts = [val for pair in zip(parts, missing_strings)
                         for val in pair][:-1]

                written = 0
                style_idx = 0
                for part in parts:
                    self.win.addstr(line, written, part, styles[style_idx])
                    written += len(part)
                    style_idx = (style_idx+1) % 2
            else:
                self.win.addstr(line, 0, string, normal_style)

        self.win.refresh()

    def show_help(self, keymap):
        lines = keymap.map_to_help(self.key_class)
        PopupArea(self.screen, (self.height, self.width), lines, self.cursor,
                  print_infos=self.print_infos)
        self.display(redraw=True)

    def show_infos(self):
        item = self.get_current_item()
        lines = self.item_to_string(item, multi_lines=True)

        PopupArea(self.screen, (self.height, self.width), lines, self.cursor,
                  print_infos=self.print_infos)
        self.display(redraw=True)

    def show_description(self):
        item = self.get_current_item()
        lines = item['description'].split('\n')

        PopupArea(self.screen, (self.height, self.width), lines, self.cursor,
                  print_infos=self.print_infos)
        self.display(redraw=True)

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

        self.last_selected_item = self.items[self.selection[idx]]
        self.display(redraw)

    def reset_display(self):
        self.old_cursor = 0
        self.cursor = 0
        self.first_line = 0
        self.display(True)

    def display(self, redraw=False):
        self.shown = True

        if self.contents is None:
            redraw = True
            self.add_contents()
            return

        self.mutex.acquire()

        if self.contents and redraw:
            if self.last_selected_item is not None:
                # Set cursor on the same item than before redisplay
                for global_idx in \
                        range(self.last_selected_item['index'],
                              self.selection[-1]+1):
                    try:
                        idx = self.selection.index(global_idx)
                    except ValueError:
                        self.first_line, self.cursor = (0, 0)
                        self.last_selected_item = self.items[self.selection[0]]
                        redraw = True
                    else:
                        self.first_line, self.cursor = \
                            self.idx_to_position(idx)
                        self.last_selected_item = \
                            self.items[self.selection[idx]]
                        redraw = True
                        break
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
            self.user_selection = []  # reset user selection

            for line_number in range(self.height):
                if self.first_line+line_number < len(self.contents):
                    line = self.contents[self.first_line+line_number]
                    # Line where cursor is, bold
                    if line_number == self.cursor:
                        self.print_line(line_number, line, True)
                    else:
                        self.print_line(line_number, line)

                # Erase previous text for empty lines (bottom of scroll)
                else:
                    self.print_line(line_number, '')

        elif self.old_cursor != self.cursor:
            self.print_line(self.old_cursor,
                            self.contents[self.first_line+self.old_cursor])
            self.print_line(self.cursor,
                            self.contents[self.first_line+self.cursor], True)

        self.mutex.release()

    def get_key_class(self):
        return self.key_class


class MediumArea(ItemArea):
    def __init__(self, screen, location, items, name, title_area, print_infos):
        self.location = location
        self.state = 'unread'
        self.key_class = 'media_'+location
        self.channel_filter = False

        super().__init__(screen, items, location, name, title_area,
                         print_infos)

    def get_title_name(self):
        return '%s (%s)' % (self.display_name, self.state)

    def extract_channel_name(self, line):
        return line.split(u" \u2022 ")[1]

    def get_current_channel(self):
        line = self.get_current_line()
        return self.extract_channel_name(line)

    def channel_filter_switch(self, channel=None):
        if channel is None and self.channel_filter:
            self.channel_filter = False
        else:
            if channel is None:
                channel = self.get_current_channel()
            self.channel_filter = channel

        # Update screen
        self.reset_contents()

    def switch_state(self):
        states = ['all', 'unread', 'read', 'skipped']
        idx = states.index(self.state)
        self.state = states[(idx+1) % len(states)]
        self.print_infos('Show %s media' % self.state)
        self.title_area.print(self.get_title_name())
        self.reset_contents()

    # if new_items update selection (do not replace)
    def filter(self, new_items):
        matching_items = []
        other_items = []
        for item in new_items:
            match = True
            if self.channel_filter and self.channel_filter != item['channel']:
                match = False
            elif self.location != item['location']:
                match = False
            elif 'all' != self.state and self.state != item['state']:
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
            fields = ['title', 'channel', 'date', 'duration', 'filename']
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
        super().__init__(screen, items, name, display_name, title_area,
                         print_infos)

    def get_title_name(self):
        return self.display_name

    def filter(self, channels):
        # TODO add filter
        return channels, []

    def item_to_string(self, channel, multi_lines=False, width=None):
        date = ts_to_date(channel['updated'])

        url = channel['url']
        unread_elements = self.data_base.channel_get_unread_media(url)
        total_elements = self.data_base.channel_get_all_media(url)
        separator = u" \u2022 "

        # TODO format and align
        string = channel['title']
        string += separator
        string += channel['type']
        string += separator
        string += '%d/%d' % (len(unread_elements), len(total_elements))
        string += separator
        string += channel['genre']
        string += separator
        string += channel['auto']
        string += separator
        string += date

        return string


class TitleArea:
    def __init__(self, screen, title):
        height, width = screen.getmaxyx()
        self.height = 1
        self.width = width-1
        self.win = curses.newwin(self.height, self.width, 0, 0)
        self.win.bkgd(curses.color_pair(3))
        self.win.keypad(1)
        self.print(title)

    def print(self, string):
        self.win.move(0, 0)
        self.win.clrtoeol()
        self.win.addstr(0, 0, str(string))
        self.win.refresh()


class StatusArea:
    def __init__(self, screen):
        height, width = screen.getmaxyx()
        self.height = 1
        self.width = width-1
        self.win = curses.newwin(self.height, self.width, height-1, 0)
        self.win.bkgd(curses.color_pair(3))
        self.win.keypad(1)
        self.print('')

    def print(self, value):
        string = str(value)
        print_log(string)
        if len(string)+1 > self.width:
            short_string = string[:self.width-4]+'.'*3
        else:
            short_string = string

        self.win.move(0, 0)
        self.win.clrtoeol()
        self.win.addstr(0, 0, str(short_string))
        self.win.refresh()

    def run_command(self, prefix):
        self.print(prefix)
        tb = curses.textpad.Textbox(self.win)
        string = tb.edit()[len(prefix):-1]  # remove prefix and last char
        return string


class PopupArea:
    def __init__(self, screen, area_size, raw_lines, base, margin=5,
                 print_infos=print):
        screen_height, screen_width = area_size

        self.outer_margin = margin
        self.inner_margin = 2
        self.width = screen_width-self.outer_margin*2
        self.text_width = self.width-self.inner_margin*2

        lines = []
        for l in raw_lines:
            lines.extend(format_string(l, self.text_width, truncate=False))

        self.height = len(lines)+2  # for border

        # Compute first line position
        if self.height > screen_height:
            lines = lines[:screen_height-2]
            lines[-1] = lines[-1][:-1]+'…'
            print_infos('Truncated, too many lines!')
            self.height = len(lines)+2

        start = max(1, base-int(len(lines)/2))
        if start+self.height-1 > screen_height:
            start = screen_height-1-self.height

        self.win = curses.newwin(self.height, self.width, start,
                                 self.outer_margin)
        self.win.bkgd(curses.color_pair(3))
        self.win.keypad(1)
        self.win.border('|', '|', '-', '-', '+', '+', '+', '+')

        for line in range(len(lines)):
            self.win.move(line+1, self.inner_margin)
            self.win.addstr(line+1, self.inner_margin, str(lines[line]))
        self.win.refresh()

        key = screen.getch()
        curses.ungetch(key)
