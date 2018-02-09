import configparser
import appdirs
import os
from os.path import expanduser

from keymap import defaultKeymaps

def createDefaultConfig(configPath):
    config['Global'] = { 'mediaDir': expanduser("~")+'/pypod' }

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

appname = 'pypod'
appauthor = 'pypod'

configDir = appdirs.user_config_dir(appname, appauthor)
if not os.path.exists(configDir):
    os.makedirs(configDir)

cacheDir = appdirs.user_cache_dir(appname, appauthor)
if not os.path.exists(cacheDir):
    os.makedirs(cacheDir)

configPath = configDir+'/pypod.ini'
dbPath = configDir+'/pypod.db'
logPath = cacheDir+'/pypod.log'

config = configparser.ConfigParser()
if not os.path.exists(configPath):
    createDefaultConfig(configPath)
else:
    config.read(configPath)

mediaPath = config['Global']['mediaDir']
if not os.path.exists(mediaPath):
    os.makedirs(mediaPath)

keys = config['Keymap']
