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

import termipod.config as Config


keycodes = {}
keynames = {}
lastkey = None
keymap = None
mousecodes = {}


def get_key(screen):
    global lastkey
    key = screen.getch()
    lastkey = key

    key_name = get_key_name(key)

    mouse = None
    if key_name == 'KEY_MOUSE':
        try:
            mouse = curses.getmouse()
            key = mouse[4]
            key_name = get_mouse_codes(key)
        except curses.error:
            return None

    return key, key_name, mouse


def get_last_key():
    return lastkey


def keycode_to_keyname(screen, key):
    key_name = curses.keyname(key).decode()
    if ' ' == key_name:
        key_name = 'KEY_SPACE'
    elif '^J' == key_name:
        key_name = '\n'
    elif '^I' == key_name:
        key_name = '\t'
    return key_name


def init_key_tables(screen):
    # for i in range(0x110000):
    for i in range(500):
        keyname = keycode_to_keyname(screen, i)
        if keyname != '':
            keycodes[keyname] = i
            keynames[i] = keyname

    keys = (
        'BUTTON1_PRESSED',
        'BUTTON1_RELEASED',
        'BUTTON1_CLICKED',
        'BUTTON1_DOUBLE_CLICKED',
        'BUTTON1_TRIPLE_CLICKED',
        'BUTTON2_PRESSED',
        'BUTTON2_RELEASED',
        'BUTTON2_CLICKED',
        'BUTTON2_DOUBLE_CLICKED',
        'BUTTON2_TRIPLE_CLICKED',
        'BUTTON3_PRESSED',
        'BUTTON3_RELEASED',
        'BUTTON3_CLICKED',
        'BUTTON3_DOUBLE_CLICKED',
        'BUTTON3_TRIPLE_CLICKED',
        'BUTTON4_PRESSED',
        'BUTTON4_RELEASED',
        'BUTTON4_CLICKED',
        'BUTTON4_DOUBLE_CLICKED',
        'BUTTON4_TRIPLE_CLICKED',
        'BUTTON_SHIFT',
        'BUTTON_CTRL',
        'BUTTON_ALT',
    )
    for k in keys:
        mousecodes[getattr(curses, k)] = k


def get_mouse_codes(state):
    try:
        return mousecodes[state]
    except KeyError:  # weird behavior of curses
        # We use state value directly
        return f'KEY_MOUSE:{state}'


def get_key_code(key_name):
    try:
        return keycodes[key_name]
    except KeyError:
        # If we have a mouse code
        km_prefix = 'KEY_MOUSE:'
        if key_name.startswith(km_prefix):
            return int(key_name[len(km_prefix):])

        else:
            return getattr(curses, key_name)


def get_key_name(key_code):
    if key_code == -1:
        return None
    return keynames[key_code]


def get_keymap():
    return keymap


class Keymap():
    def __init__(self):
        self.keymaps = self.load_keymap(Config.get('Keymap'))

        self.keys = {}
        self.actions = {}
        for m in self.keymaps:
            self.add_key(*m)
        global keymap
        keymap = self

    def add_key(self, area_type, key, action):
        if key not in keycodes:
            # If not mouse button
            if (not hasattr(curses, key)
                    and not key.startswith('KEY_MOUSE:')):
                raise ValueError(
                    f"Key '{key}' for {action} is not handled, "
                    "please fix your config file (or remove Keymap section "
                    "to have default key binding")
        self.keys[(area_type, key)] = action
        if action not in self.actions:
            self.actions[action] = []
        self.actions[action].append(key)

    def list_keys(self):
        return [k[1] for k in self.keys.keys()]

    def get_action(self, area_type, key_name):
        sub_type = area_type.split('_')[0]
        for t in (area_type, sub_type, ''):
            if (t, key_name) in self.keys:
                return self.keys[(t, key_name)]
        return None

    def get_keys(self, action):
        return tuple(self.actions[action])

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
            if action[0] == '~':
                action = action[1:]

            if not key_list:
                key_list = '<empty>'
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

                for w in where.split(','):
                    keymaps.append((w, key, action))

        keymaps.append(('', 'KEY_RESIZE', 'resize'))
        return keymaps


descriptions = {
        'line_down': 'Go one line down',
        'line_up': 'Go one line up',
        'page_down': 'Go one page down',
        'page_up': 'Go one page up',
        'top': 'Go top',
        'bottom': 'Go bottom',
        'move_line': 'Move to mouse position',
        'tab_next': 'Go next tab',
        'tab_prev': 'Go previous tab',
        'help': 'Show help',

        'refresh': 'Redraw screen',
        'resize': 'Resize screen',
        'reset': 'Reset screen',

        'screen_infos': 'Show screen information',

        'command_get': 'Command input',
        'search_get': 'Search pattern',
        'search_next': 'Move to next search pattern',
        'search_prev': 'Move to previous search pattern',

        'quit': 'Quit',

        'channel_update': 'Update channels',

        'select_item': 'Select item',
        'select_until': 'Grow selection',
        'select_clear': 'Clear selection',

        'sort': 'Change item sorting (date+name, duration, name)',
        'sort_reverse': 'Reverse sort order',

        'show_cursor_bg': 'Black bg on current line',

        'url_copy': 'Copy urls to clipbooard',

        'filter_clear': 'Clear filters',

        'search_channel': 'Highlight channel',
        'medium_play': 'Play media',
        'medium_playadd': 'Enqueue media',
        'medium_stop': 'Stop playing',
        'medium_remove': 'Mark as read and remove local file',
        'medium_read': 'Mark as read/unread',
        'medium_skip': 'Mark/Unmark as skipped',
        'medium_update': 'Update media',
        'channel_filter': 'Filter same channel',
        'category_filter': 'Filter by category',
        'state_filter': 'Change panel state view (read, unread, skipped...)',
        'state_filter_reverse': 'Change panel state view in reverse way',
        'location_filter': ('Change panel location view '
                            '(remote, download, local...)'),
        'location_filter_reverse': ('Change panel location view '
                                    'in reverse way'),
        'infos': 'Show information',
        'description': 'Show description',
        'thumbnail': 'Show/hide thumbnail (urxvt only)',
        'medium_tag': 'Set tags for media',
        'tag_filter': 'Filter by tag',
        'search_filter': 'Filter matching items',
        'selection_filter': 'Filter from selected items',
        'medium_show_channel': 'Jump to corresponding channel',

        'medium_download': 'Download / Cancel downloading / Remove file',

        'send_to_playlist': 'Send selection to a m3u playlist',
        'send_to_last_playlist': 'Send selection to last m3u playlist',

        'channel_auto': 'Set channel as auto',
        'channel_auto_custom': 'Set custom value for auto',
        'channel_show_media': 'Show media of channel',
        'channel_category': 'Add category to channel',
        'channel_mask': 'Edit channel mask',
        'channel_force_update': ('Update channels '
                                 '(check also for old elements)'),
}
