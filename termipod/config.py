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

import sys

# This is a pointer to the module object instance itself
this = sys.modules[__name__]


def init(**kwargs):
    """ kwargs: config_path, log_path, db_path, media_path
    """
    appname = 'termipod'
    appauthor = 'termipod'

    default_config_dir = appdirs.user_config_dir(appname, appauthor)
    default_cache_dir = appdirs.user_cache_dir(appname, appauthor)

    default_params = {
        'log_path': f'{default_cache_dir}/{appname}.log',
        'db_path': f'{default_config_dir}/{appname}.db',
        'thumbnail_path': f'{default_cache_dir}/thumbnails',
        'media_path': expanduser("~")+'/'+appname,
        'update_minutes': '30',
        'httpserver_port': '8195',
        'httpserver_start': '0',
        'media_reverse': '0',
        'channel_reverse': '0',
    }

    params = default_params.keys()

    # We set config_path (for config file)
    if 'config_path' in kwargs:  # If config_path is specified by user
        this.config_path = kwargs['config_path']
    else:  # default config_path
        if not os.path.exists(default_config_dir):
            os.makedirs(default_config_dir)
        this.config_path = '%s/%s.ini' % (default_config_dir, appname)

    # If config file exists, we read it and set found values
    config_parser = configparser.ConfigParser()
    if os.path.exists(this.config_path):
        config_parser.read(this.config_path)
        for param in params:
            if param in config_parser['Global']:
                setattr(this, param, config_parser['Global'][param])

    # We use values given as parameters or default values
    for param in params:
        if param in kwargs:
            setattr(this, param, kwargs[param])
        else:
            if not hasattr(this, param):
                setattr(this, param, default_params[param])

    # Set destination file for print_log
    print_log.filename = this.log_path

    # We create missing directories
    dirs = [
        os.path.dirname(this.log_path),
        os.path.dirname(this.db_path),
        this.media_path,
        this.thumbnail_path
    ]
    for d in dirs:
        if not os.path.exists(d):
            os.makedirs(d)

    # If config file does not exist, we create it
    default_keymap_config = default_keymap_to_config()
    if not os.path.exists(this.config_path):
        config_parser['Global'] = {}
        for param in params:
            config_parser['Global'][param] = getattr(this, param)

        config_parser['Keymap'] = default_keymap_config

        # We create the config file
        with open(this.config_path, 'w') as f:
            config_parser.write(f)

    # If we already have a config file, we still check there is no new
    # parameters available or we add them
    else:
        new_param = False
        for param in params:
            if param not in config_parser['Global']:
                new_param = True
                config_parser['Global'][param] = getattr(this, param)

        # Keymap
        keymap_config = config_parser.setdefault('Keymap', {})

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
                    if key_seq in value.split(' '):
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
            del config_parser['Keymap'][action]

        if new_param or new_actions or old_actions:
            # We update the config file
            with open(this.config_path, 'w') as f:
                config_parser.write(f)

    this.keys = config_parser['Keymap']

    # Cast integer parameters
    for p in ('update_minutes', 'media_reverse', 'channel_reverse',
              'httpserver_port', 'httpserver_start'):
        setattr(this, p, int(getattr(this, p)))


def default_keymap_to_config():
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

        ('*', '^L', 'refresh'),
        ('*', '^G', 'screen_infos'),

        ('*', ':', 'command_get'),
        ('*', '/', 'search_get'),
        ('*', 'n', 'search_next'),
        ('*', 'N', 'search_prev'),

        ('*', '^?', 'filter_clear'),

        ('*', 'q', 'quit'),

        ('*', 'u', 'channel_update'),
        ('*', 'i', 'infos'),
        ('*', 'v', 'thumbnail'),
        ('*', 'V', 'show_cursor_bg'),

        ('*', 'KEY_SPACE', 'select_item'),
        ('*', '$', 'select_until'),
        ('*', '^', 'select_clear'),

        ('*', 'e', 'category_filter'),

        ('*', 's', 'sort'),
        ('*', 'S', 'sort_reverse'),

        ('*', 'y', 'url_copy'),

        ('media', '*', 'search_channel'),
        ('media', 'l', 'medium_play'),
        ('media', '\n', 'medium_playadd'),
        ('media', 'h', 'medium_stop'),
        ('media', 'r', 'medium_read'),
        ('media', 'R', 'medium_skip'),
        ('media', 'U', 'medium_update'),
        ('media', 'c', 'channel_filter'),
        ('media', 'C', 'medium_show_channel'),
        ('media', 'f', 'state_filter'),
        ('media', 'F', 'state_filter_reverse'),
        ('media', 'a', 'location_filter'),
        ('media', 'A', 'location_filter_reverse'),
        ('media', 'I', 'description'),
        ('media', 'T', 'medium_tag'),
        ('media', 't', 'tag_filter'),
        ('media', 'd', 'medium_download'),
        ('media', 'D', 'medium_remove'),  # only for local medium
        ('media', 'p', 'save_as_playlist'),

        ('channels', 'a', 'channel_auto'),
        ('channels', 'A', 'channel_auto_custom'),
        ('channels', '\n', 'channel_show_media'),
        ('channels', 'E', 'channel_category'),
        ('channels', 'm', 'channel_mask'),
        ('channels', 'U', 'channel_force_update'),
    ]

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
