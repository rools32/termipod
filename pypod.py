#!/usr/bin/python
import curses
import shlex

import rss
from database import DataBase
from itemlist import ItemList
from ui import TextArea, StatusArea, TitleArea


def printInfos(string):
    statusArea.print(string)


db = DataBase('pypod.db')

screen = curses.initscr()
height,width = screen.getmaxyx()
#printLog('Height: %d, Width: %d' % (height, width))
screen.immedok(True)
curses.start_color()
curses.curs_set(0) # disable cursor
curses.cbreak() # no need to press enter to react to keys
curses.noecho() # do not show pressed keys
curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)
curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_BLACK)
curses.init_pair(3, curses.COLOR_BLACK, curses.COLOR_WHITE)
curses.init_pair(4, curses.COLOR_RED, curses.COLOR_BLACK)
screen.refresh()

statusArea = StatusArea(screen)

itemList = ItemList(db.selectVideos(), db, statusArea.print)
tabs = []
tabnames = []

# New tab
tabs.append(TextArea(screen, itemList, 'new', statusArea.print))
newStr = 'New feeds'
tabnames.append(newStr)

# Play tab
tabs.append(TextArea(screen, itemList, 'downloaded', statusArea.print))
playStr = 'Play'
tabnames.append(playStr)

curTab = 0
tab = tabs[curTab]
tab.display(True)
tab.shown = True

titleArea = TitleArea(screen, tabnames[curTab])

while True:
    # Wait for key
    key = screen.getch()
    statusArea.print(str(key))
    idx = tab.getIdx()

    what = None
    if key in (ord('j'), curses.KEY_DOWN):
        what = 'line'
        way = 'down'
    elif key == ord('k'):
        what = 'line'
        way = 'up'
    elif key == 6:
        what = 'page'
        way = 'down'
    elif key == 2:
        what = 'page'
        way = 'up'
    elif key == ord('g'):
        what = 'all'
        way = 'up'
    elif key == ord('G'):
        what = 'all'
        way = 'down'

    if what:
        tab.moveScreen(what, way)
    elif key == ord(':'):
        string = statusArea.runCommand(':')
        command = shlex.split(string)
        printInfos('Run: '+str(command))
        if command[0] in ('q', 'quit'):
            exit()
        elif command[0] in ('h', 'help'):
            printInfos('Help!!!!!!')
        elif command[0] in ('add',):
            if 1 == len(command):
                addHelp = 'Usage: add url [auto] [genre]'
                printInfos(addHelp)
            else:
                printInfos('Add '+command[1])
                msg = rss.addChannel(db, tab, *command[1:])
                printInfos(msg)


    elif key == ord('q'):
        break
    elif key == ord('\n'):
        tab.itemList.download(idx)
    elif key == ord('u'):
        printInfos('Update...')
        updated = rss.updateVideos(db)
        if updated:
            tab.updateItems(db.selectVideos())

    elif key == ord('/'):
        searchString = statusArea.runCommand('/')
        printInfos('Search: '+searchString)
        tab.highlight(searchString)
    elif key == ord('n'):
        tab.nextHighlight()
    elif key == ord('*'):
        line = tab.getCurrentLine()
        channel = line.split(u" \u2022 ")[1]
        printInfos('Search: '+channel)
        tab.highlight(channel)

    elif key == ord('\t'):
        tab.shown = False
        curTab = (curTab+1)%len(tabs)
        tab = tabs[curTab]
        tab.shown = True
        titleArea.print(tabnames[curTab])
        tab.display(True)
