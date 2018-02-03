import configparser
import appdirs
import os
from os.path import expanduser

def createDefaultConfig():
    config['Global'] = { 'mediaDir': expanduser("~")+'/pypod' }
    with open(configFile, 'w') as f:
        config.write(f)

appname = 'pypod'
appauthor = 'pypod'

configDir = appdirs.user_config_dir(appname, appauthor)
if not os.path.exists(configDir):
    os.makedirs(configDir)

cacheDir = appdirs.user_cache_dir(appname, appauthor)
if not os.path.exists(cacheDir):
    os.makedirs(cacheDir)

configFile = configDir+'/pypod.ini'
dbFile = configDir+'/pypod.db'
logFile = cacheDir+'/pypod.log'

config = configparser.ConfigParser()
if not os.path.exists(configFile):
    createDefaultConfig()
else:
    config.read(configFile)

mediaDir = config['Global']['mediaDir']
if not os.path.exists(mediaDir):
    os.makedirs(mediaDir)
