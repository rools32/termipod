#!/usr/bin/python
from ui import UI
import argparse
import sys
import os

from itemlist import ItemList
import config

# Instantiate the parser
parser = argparse.ArgumentParser(\
        description='Manage your podcasts\nNo argument for UI')
parser.add_argument('--add', type=str, help='Add channel')
parser.add_argument('--auto', type=str, help='Auto filter (regex)')
parser.add_argument('--up', action='store_true', help='Update channels')
args = parser.parse_args()

dbName = config.dbFile
os.chdir(config.mediaDir)

if len(sys.argv) == 1:
    UI(dbName)

else:
    itemList = ItemList(dbName, wait=True)

    if args.up:
        itemList.updateVideoList()
    if args.add:
        auto = ''
        if args.auto:
            auto = args.auto
        itemList.addChannel(args.add, auto=auto)
