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

import yaml
import os
from os.path import expanduser
import collections.abc

import appdirs
import sys

# This is a pointer to the module object instance itself
this = sys.modules[__name__]

flat_commandline_config = {}
config = {}

default_params = {}


def init(**kwargs):
    """ kwargs: config_path, log_path, db_path, media_path
    """
    appname = 'termipod'
    appauthor = 'termipod'

    default_config_dir = appdirs.user_config_dir(appname, appauthor)
    default_cache_dir = appdirs.user_cache_dir(appname, appauthor)

    default = {
        'Global.log_path': f'{default_cache_dir}/{appname}.log',
        'Global.db_path': f'{default_config_dir}/{appname}.db',
        'Global.thumbnail_path': f'{default_cache_dir}/thumbnails',
        'Global.media_path': expanduser("~")+'/'+appname,
        'Global.update_minutes': 30,
        'Global.httpserver_port': 8195,
        'Global.httpserver_start': False,
        'Global.media_reverse': False,
        'Global.channel_reverse': False,
        'Global.thumbnail_max_total_mb': 256,
        'Tabs': [],
    }
    default_params.update(default)

    params = default_params.keys()

    # We set config_path (for config file)
    if 'config_path' in kwargs:  # If config_path is specified by user
        this.config_path = kwargs['config_path']
        del kwargs['config_path']
    else:  # default config_path
        if not os.path.exists(default_config_dir):
            os.makedirs(default_config_dir)
        this.config_path = '%s/%s.yaml' % (default_config_dir, appname)

    # Check no unknown option given in command line
    # We use values given as parameters
    for param in kwargs:
        if param not in params:
            raise ValueError('Unknown options: '+param)
        flat_commandline_config[param] = kwargs[param]

    # Fill config with default values
    for param in params:
        this.set(param, default_params[param], create=True)

    # Add default keymap
    default_keymap_config = default_keymap_to_config()
    config['Keymap'] = default_keymap_config
    this.keys = config['Keymap']

    # If config file exists, we read it and set found values
    if os.path.exists(this.config_path):
        with open(this.config_path, 'r') as stream:
            config_from_file = yaml.safe_load(stream)
            update_config(config, config_from_file)
    # TODO check keys appear only once

    # We create missing directories
    dirs = [
        os.path.dirname(config['Global']['log_path']),
        os.path.dirname(config['Global']['db_path']),
        config['Global']['media_path'],
        config['Global']['thumbnail_path']
    ]
    for d in dirs:
        if not os.path.exists(d):
            os.makedirs(d)

    write()


def save_tabs(params):
    config['Tabs'] = params
    write()


def write():
    with open(this.config_path, 'w') as f:
        yaml.dump(config, f,
                  default_flow_style=False, allow_unicode=False)


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
        ('*', '^R', 'reset'),
        ('*', '^G', 'screen_infos'),

        ('*', ':', 'command_get'),
        ('*', '/', 'search_get'),
        ('*', 'n', 'search_next'),
        ('*', 'N', 'search_prev'),

        ('*', '^?', 'filter_clear'),

        ('*', 'q', 'quit'),

        ('*', 'i', 'infos'),
        ('*', 'v', 'thumbnail'),
        ('*', 'V', 'show_cursor_bg'),

        ('*', 'KEY_SPACE', 'select_item'),
        ('*', '$', 'select_until'),
        ('*', '^', 'select_clear'),


        ('*', 's', 'sort'),
        ('*', 'S', 'sort_reverse'),

        ('*', 'y', 'url_copy'),

        ('*', '%', 'search_filter'),
        ('*', 'o', 'selection_filter'),

        ('media,search', 'l', 'medium_play'),
        ('media,search', '\n', 'medium_playadd'),
        ('media,search', 'U', 'medium_update'),
        ('media,search', 'p', 'save_as_playlist'),
        ('media,search', 'I', 'description'),

        ('media,channels', 'e', 'category_filter'),
        ('media,channels', 'u', 'channel_update'),

        ('media', '*', 'search_channel'),
        ('media', 'h', 'medium_stop'),
        ('media', 'r', 'medium_read'),
        ('media', 'R', 'medium_skip'),
        ('media', 'c', 'channel_filter'),
        ('media', 'C', 'medium_show_channel'),
        ('media', 'f', 'state_filter'),
        ('media', 'F', 'state_filter_reverse'),
        ('media', 'a', 'location_filter'),
        ('media', 'A', 'location_filter_reverse'),
        ('media', 'T', 'medium_tag'),
        ('media', 't', 'tag_filter'),
        ('media', 'd', 'medium_download'),
        ('media', 'D', 'medium_remove'),  # only for local medium

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


def update_config(d, u):
    for k, v in u.items():
        if k not in d:
            raise ValueError('Unknown option: '+k)
        if isinstance(v, collections.abc.Mapping):
            d[k] = update_config(d.get(k, {}), v)
        else:
            d[k] = v
    return d


def str_to_config_path(what, create=False):
    target = config
    path = what.split('.')
    last = path[-1]
    path = path[:-1]

    for p in path:
        if create:
            target = target.setdefault(p, {})
        else:
            target = target[p]

    return target, last


def get(what):
    # From string to right type
    try:
        caster = type(default_params[what])
    except KeyError:
        raise ValueError('Unknown option '+what)

    if what in flat_commandline_config:
        return caster(flat_commandline_config[what])

    target, field = str_to_config_path(what)
    return caster(target[field])


def set(what, value, create=False):
    # From string to right type
    try:
        value = type(default_params[what])(value)
    except KeyError:
        raise ValueError('Unknown option '+what)

    if what in flat_commandline_config:
        del flat_commandline_config[what]

    target, field = str_to_config_path(what, create)
    target[field] = value
