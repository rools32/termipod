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

import configparser
import os
from os.path import expanduser

import appdirs

from termipod.utils import print_log

appname = 'termipod'
appauthor = 'termipod'

default_config_dir = appdirs.user_config_dir(appname, appauthor)
default_cache_dir = appdirs.user_cache_dir(appname, appauthor)

default_params = {
    'log_path': '%s/%s.log' % (default_cache_dir, appname),
    'db_path': '%s/%s.db' % (default_config_dir, appname),
    'media_path': expanduser("~")+'/'+appname,
}

default_keymaps = [
    ('*', 'j', 'line_down'),
    ('*', 'KEY_DOWN', 'line_down'),
    ('*', 'k', 'line_up'),
    ('*', 'KEY_UP', 'line_up'),
    ('*', '^F', 'page_down'),
    ('*', 'KEY_NPAGE', 'page_down'),
    ('*', 'KEY_RIGHT', 'page_down'),
    ('*', '^B', 'page_up'),
    ('*', 'KEY_PPAGE', 'page_up'),
    ('*', 'KEY_LEFT', 'page_up'),
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

    ('*', 'u', 'channel_update'),
    ('*', 'i', 'infos'),

    ('*', 'KEY_SPACE', 'select_item'),
    ('*', '$', 'select_until'),
    ('*', '^', 'select_clear'),

    ('media', '*', 'search_channel'),
    ('media', 'l', 'medium_play'),
    ('media', 'a', 'medium_playadd'),
    ('media', 'h', 'medium_stop'),
    ('media', 'r', 'medium_read'),
    ('media', 'R', 'medium_skip'),
    ('media', 'U', 'medium_update'),
    ('media', 's', 'medium_sort'),
    ('media', 'c', 'channel_filter'),
    ('media', 'e', 'category_filter'),
    ('media', 'f', 'state_filter'),
    ('media', 'I', 'description'),  # TODO for channels too (s/'media'/'')

    ('media_remote', '\n', 'medium_download'),

    ('media_local', '\n', 'medium_playadd'),
    ('media_local', 'd', 'medium_download'),
    ('media_local', 'D', 'medium_remove'),

    ('media_download', 'd', 'medium_download'),


    ('channels', 'a', 'channel_auto'),
    ('channels', 'A', 'channel_auto_custom'),
    ('channels', '\n', 'channel_show_media'),
    ('channels', 't', 'channel_category'),
]


class Config():
    def __init__(self, **kwargs):
        """ kwargs: config_path, log_path, db_path, media_path
        """
        params = default_params.keys()

        # We set config_path (for config file)
        if 'config_path' in kwargs:  # If config_path is specified by user
            self.config_path = kwargs['config_path']
        else:  # default config_path
            if not os.path.exists(default_config_dir):
                os.makedirs(default_config_dir)
            self.config_path = '%s/%s.ini' % (default_config_dir, appname)

        # If config file exists, we read it and set found values
        self.config_parser = configparser.ConfigParser()
        if os.path.exists(self.config_path):
            self.config_parser.read(self.config_path)
            for param in params:
                if param in self.config_parser['Global']:
                    setattr(self, param, self.config_parser['Global'][param])

        # We use values given as parameters or default values
        for param in params:
            if param in kwargs:
                setattr(self, param, kwargs[param])
            else:
                if not hasattr(self, param):
                    setattr(self, param, default_params[param])

        # Set destination file for print_log
        print_log.filename = self.log_path

        # We create missing directories
        dirs = [os.path.dirname(self.log_path),
                os.path.dirname(self.db_path), self.media_path]
        for d in dirs:
            if not os.path.exists(d):
                os.makedirs(d)

        # If config file does not exist, we create it
        default_keymap_config = self.default_keymap_to_config()
        if not os.path.exists(self.config_path):
            self.config_parser['Global'] = {}
            for param in params:
                self.config_parser['Global'][param] = getattr(self, param)

            self.config_parser['Keymap'] = default_keymap_config

            # We create the config file
            with open(self.config_path, 'w') as f:
                self.config_parser.write(f)

        # If we already have a config file, we still check there is no new
        # parameters available or we add them
        else:
            # Paths
            new_param = False
            for param in params:
                if param not in self.config_parser['Global']:
                    new_param = True
                    self.config_parser['Global'][param] = getattr(self, param)

            # Keymap
            keymap_config = self.config_parser['Keymap']
            # Add new actions
            new_actions = [a for a in default_keymap_config
                           if a not in keymap_config]
            for action in new_actions:
                key_seqs = default_keymap_config[action].split(' ')

                new_key_seqs = []
                for key_seq in key_seqs:
                    # If key sequence is available, we add it
                    found = False
                    for value in keymap_config.values():
                        if key_seq in value:
                            found = True
                            break
                    if not found:
                        new_key_seqs.append(key_seq)

                if new_key_seqs:
                    keymap_config[action] = ' '.join(new_key_seqs)
                # If no key sequence available, we set an empty sequence with
                # the area of the first key sequence
                else:
                    key_seq = key_seqs[0]
                    keymap_config[action] = key_seq[:key_seq.index('/')+1]

            # Remove deleted actions
            old_actions = [a for a in keymap_config
                           if a not in default_keymap_config]
            for action in old_actions:
                del self.config_parser['Keymap'][action]

            if new_param or new_actions or old_actions:
                # We update the config file
                with open(self.config_path, 'w') as f:
                    self.config_parser.write(f)

        self.keys = self.config_parser['Keymap']

    def default_keymap_to_config(self):
        # Write default keymaps
        keys = {}
        for (where, key, action) in default_keymaps:
            if action in keys:
                value = keys[action]+' '
            else:
                value = ''

            key = "%r" % key  # raw key
            value += "%s/%s" % (where, key[1:-1])

            keys[action] = value
        return keys
