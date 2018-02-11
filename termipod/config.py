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

import configparser
import os
from os.path import expanduser

import appdirs

from termipod.keymap import default_keymaps

appname = 'termipod'
appauthor = 'termipod'


def create_default_config(config_path):
    config['Global'] = {'media_dir': expanduser("~")+'/'+appname}

    # Write default keymaps
    config['Keymap'] = {}
    for (where, key, action) in default_keymaps:
        if action in config['Keymap']:
            value = config['Keymap'][action]+' '
        else:
            value = ''

        key = "%r" % key  # raw key
        value += "%s/%s" % (where, key[1:-1])

        config['Keymap'][action] = value

    with open(config_path, 'w') as f:
        config.write(f)


config_dir = appdirs.user_config_dir(appname, appauthor)
if not os.path.exists(config_dir):
    os.makedirs(config_dir)

cache_dir = appdirs.user_cache_dir(appname, appauthor)
if not os.path.exists(cache_dir):
    os.makedirs(cache_dir)

config_path = '%s/%s.ini' % (config_dir, appname)
db_path = '%s/%s.db' % (config_dir, appname)
log_path = '%s/%s.log' % (cache_dir, appname)

config = configparser.ConfigParser()
if not os.path.exists(config_path):
    create_default_config(config_path)
else:
    config.read(config_path)

media_path = config['Global']['media_dir']
if not os.path.exists(media_path):
    os.makedirs(media_path)

keys = config['Keymap']
