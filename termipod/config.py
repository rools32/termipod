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

from termipod.keymap import defaultKeymaps

appname = 'termipod'
appauthor = 'termipod'

def createDefaultConfig(configPath):
    config['Global'] = { 'mediaDir': expanduser("~")+'/'+appname }

    # Write default keymaps
    config['Keymap'] = {}
    for (where, key, action) in defaultKeymaps:
        if action in config['Keymap']:
            value = config['Keymap'][action]+' '
        else:
            value = ''

        key = "%r" % key # raw key
        value += "%s/%s" % (where, key[1:-1])

        config['Keymap'][action] = value

    with open(configPath, 'w') as f:
        config.write(f)

configDir = appdirs.user_config_dir(appname, appauthor)
if not os.path.exists(configDir):
    os.makedirs(configDir)

cacheDir = appdirs.user_cache_dir(appname, appauthor)
if not os.path.exists(cacheDir):
    os.makedirs(cacheDir)

configPath = '%s/%s.ini' % (configDir, appname)
dbPath = '%s/%s.db' % (configDir, appname)
logPath = '%s/%s.log' % (cacheDir, appname)

config = configparser.ConfigParser()
if not os.path.exists(configPath):
    createDefaultConfig(configPath)
else:
    config.read(configPath)

mediaPath = config['Global']['mediaDir']
if not os.path.exists(mediaPath):
    os.makedirs(mediaPath)

keys = config['Keymap']
