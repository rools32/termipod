#!/usr/bin/python
from itemlist import ItemList
from ui import start
import argparse
import sys

# Instantiate the parser
parser = argparse.ArgumentParser(\
        description='Manage your podcasts\nNo argument for UI')
parser.add_argument('--add', type=str,
                    help='Add channel')
parser.add_argument('--up', action='store_true',
                    help='Update channels')
args = parser.parse_args()

itemList = ItemList('pypod.db')

if args.up:
    itemList.updateVideos()
if args.add:
    itemList.addChannel(args.add)
if len(sys.argv) == 1:
    start(itemList)
