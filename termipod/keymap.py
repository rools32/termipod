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


def get_key_name(screen):
    key = screen.getch()
    key_name = curses.keyname(key).decode()
    if ' ' == key_name:
        key_name = 'KEY_SPACE'
    elif '^J' == key_name:
        key_name = '\n'
    elif '^I' == key_name:
        key_name = '\t'
    return key_name


class Keymap():
    def __init__(self, config):
        from termipod.config import keys
        self.keymaps = self.load_keymap(keys)

        self.keys = {}
        for m in self.keymaps:
            self.add_key(*m)

    def add_key(self, area_type, key, action):
        self.keys[(area_type, key)] = action

    def get_action(self, area_type, key_name):
        sub_type = area_type.split('_')[0]
        for t in (area_type, sub_type, ''):
            if (t, key_name) in self.keys:
                return self.keys[(t, key_name)]
        return None

    def map_to_help(self, area_type):
        max_len = 0
        keys = {}  # indexed by action
        for where, key, action in self.keymaps:
            if where in area_type:
                keyseq = key.encode('unicode_escape').decode('ASCII')

                if action in keys:
                    keys[action] += ', '+keyseq
                else:
                    keys[action] = keyseq
                max_len = max(max_len, len(keys[action]))

        lines = []
        for action, key_list in keys.items():
            num_spaces = max_len-len(key_list)+1
            lines.append('%s%s%s' %
                         (key_list, ' '*num_spaces, descriptions[action]))

        return lines

    def load_keymap(self, keys):
        keymaps = []
        raw_keymap = keys
        for action, values in raw_keymap.items():
            for value in values.split(' '):
                where = value[:value.index('/')]
                if '*' == where:
                    where = ''

                key = value[value.index('/')+1:]
                key = bytes(key, "utf-8").decode("unicode_escape")
                keymaps.append((where, key, action))

        return keymaps


default_keymaps = [
        ('*', 'j', 'line_down'),
        ('*', 'KEY_DOWN', 'line_down'),
        ('*', 'k', 'line_up'),
        ('*', 'KEY_UP', 'line_up'),
        ('*', '^F', 'page_down'),
        ('*', 'KEY_NPAGE', 'page_down'),
        ('*', '^B', 'page_up'),
        ('*', 'KEY_PPAGE', 'page_up'),
        ('*', 'g', 'top'),
        ('*', 'KEY_HOME', 'top'),
        ('*', 'G', 'bottom'),
        ('*', 'KEY_END', 'bottom'),
        ('*', '\t', 'tab_next'),
        ('*', 'KEY_BTAB', 'tab_prev'),  # shift-tab
        ('*', '?', 'help'),

        ('*', '^R', 'redraw'),
        ('*', '^L', 'refresh'),
        ('*', '^G', 'screen_infos'),

        ('*', ':', 'command_get'),
        ('*', '/', 'search_get'),
        ('*', 'n', 'search_next'),
        ('*', 'N', 'search_prev'),

        ('*', 'q', 'quit'),

        ('*', 'KEY_SPACE', 'select_item'),
        ('*', '$', 'select_until'),
        ('*', '^', 'select_clear'),

        ('media', '*', 'search_channel'),
        ('media', 'l', 'medium_play'),
        ('media', 'a', 'medium_playadd'),
        ('media', 'h', 'medium_stop'),
        ('media', 'd', 'medium_remove'),
        ('media', 'r', 'medium_read'),
        ('media', 'R', 'medium_skip'),
        ('media', 'c', 'channel_filter'),
        ('media', 's', 'state_filter'),
        ('media', 'i', 'infos'),  # TODO for channels too (s/'media'/'')
        ('media', 'I', 'description'),  # TODO for channels too (s/'media'/'')

        ('media_remote', '\n', 'medium_download'),
        ('media_remote', 'u', 'medium_update'),

        ('media_local', '\n', 'medium_playadd'),

        ('channels', 'a', 'channel_auto'),
        ('channels', 'A', 'channel_auto_custom'),
        ('channels', '\n', 'channel_show_media'),
    ]

descriptions = {
        'line_down': 'Go one line down',
        'line_up': 'Go one line up',
        'page_down': 'Go one page down',
        'page_up': 'Go one page up',
        'top': 'Go top',
        'bottom': 'Go bottom',
        'tab_next': 'Go next tab',
        'tab_prev': 'Go previous tab',
        'help': 'Show help',

        'redraw': 'Redraw all screen',
        'refresh': 'Reinit current area',

        'screen_infos': 'Show screen information',

        'command_get': 'Command input',
        'search_get': 'Search pattern',
        'search_next': 'Move to next search pattern',
        'search_prev': 'Move to previous search pattern',

        'quit': 'Quit',

        'select_item': 'Select item',
        'select_until': 'Grow selection',
        'select_clear': 'Clear selection',

        'search_channel': 'Highlight channel',
        'medium_play': 'Play media',
        'medium_playadd': 'Enqueue media',
        'medium_stop': 'Stop playing',
        'medium_remove': 'Remove media',
        'medium_read': 'Mark as read',
        'medium_skip': 'Mark as skipped',
        'channel_filter': 'Filter same channel',
        'state_filter': 'Show next state  panel',
        'infos': 'Show information',
        'description': 'Show description',

        'medium_download': 'Download media',
        'medium_update': 'Update media list',

        'channel_auto': 'Set channel as auto',
        'channel_auto_custom': 'Set custom value for auto',
        'channel_show_media': 'Show media of channel',
}
