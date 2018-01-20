#!/usr/bin/python

import logging
import subprocess
import sys
import curses
import curses.textpad

import feedparser as fp
from time import mktime
from datetime import datetime, timedelta
import sqlite3
import urllib.request
import os, os.path
import unicodedata
from pprint import pprint

import shlex


def printLog(string):
    pass
    filename = 'log.txt'
    with open(filename, 'a') as myfile:
        myfile.write(str(string)+"\n")

def tsToDate(ts):
    return datetime.fromtimestamp(int(ts)).strftime('%Y-%m-%d')

def strToFilename(string):
    return unicodedata.normalize('NFKD', string).encode('ascii', 'ignore')\
            .decode('ascii').replace(' ', '-')

def printInfos(string):
    statusArea.print(string)

class DataBase:
    def __init__(self, name):
        self.conn = sqlite3.connect(name)
        #conn = sqlite3.connect(':memory:')
        self.cursor = self.conn.cursor()

        self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = map(lambda x: x[0], self.cursor.fetchall())

        if not 'channels' in tables:
            self.cursor.executescript("""
                CREATE TABLE channels (
                    url str PRIMARY KEY,
                    title STR,
                    type STR,
                    genre STR,
                    auto INT,
                    last_update INT
                );
            """)
        if not 'videos' in tables:
            self.cursor.executescript("""
                CREATE TABLE videos (
                    channel_url str,
                    title str,
                    date int,
                    duration int,
                    url str,
                    status int,
                    filename str,
                    tags str,
                    PRIMARY KEY (channel_url, title, date)
                );
            """)

    def selectVideos(self, what=None, value=None):
        self.cursor.execute("SELECT * FROM videos")
        # TODO
        #self.cursor.execute("SELECT * FROM tasks WHERE priority=?", (priority,))
        rows = self.cursor.fetchall()
        return list(map(self.videoListToDict, rows))

    def videoListToDict(self, videoList):
        url = videoList[0]
        channel = self.getChannel(url)['title']
        data = {}
        data['url'] = url
        data['channel'] = channel
        data['title'] = videoList[1]
        data['date'] = videoList[2]
        data['duration'] = videoList[3]
        data['link'] = videoList[4]
        data['status'] = videoList[5]
        data['filename'] = videoList[6]
        data['tag'] = videoList[7]
        return data

    def getChannel(self, url):
        """ Get Channel by url (primary key) """
        self.cursor.execute("SELECT * FROM channels WHERE url=?", (url,))
        rows = self.cursor.fetchall()
        if 1 != len(rows):
            return None
        return self.channelListToDict(rows[0])

    def selectChannels(self):
        # TODO add filters: genre, auto
        self.cursor.execute("SELECT * FROM channels")
        rows = self.cursor.fetchall()
        return list(map(self.channelListToDict, rows))

    def channelListToDict(self, channelList):
        data = {}
        data['url'] = channelList[0]
        data['title'] = channelList[1]
        data['type'] = channelList[2]
        data['genre'] = channelList[3]
        data['auto'] = channelList[4]
        data['updated'] = channelList[5]
        return data

    def addChannel(self, url, title, feedtype, genre, auto, data):
        # use chennelDictoToList TODO
        channel = [ url, title, feedtype, genre, auto, 0]
        self.cursor.execute('INSERT INTO channels VALUES (?,?,?,?,?,?)',
                 channel)
        self.conn.commit()

    def addVideos(self, data):
        updated = False
        url = data['url']

        channel = self.getChannel(url)
        if None == channel:
            return None

        # Find out if feed has updates
        updatedDate = channel['updated']
        feedDate = data['updated']
        if (feedDate > updatedDate): # new items
            # Filter feed to keep only new items
            newVideos = [ (data['url'], v['title'], v['date'],
                v['duration'], v['link'], 'new', '', '')
                for v in data['items'] if v['date'] > updatedDate ]

            if len(newVideos):
                updated = True

            # Add new items to database
            self.cursor.executemany('INSERT INTO videos VALUES (?,?,?,?,?,?,?,?)',
                    newVideos)
            self.conn.commit()

        if updated:
            self.channelUpdate(url, feedDate)

        return updated

    def channelUpdate(self, url, date):
        self.cursor.execute("UPDATE channels SET last_update = ? WHERE url = ?",
                [date, url])
        self.conn.commit()

    def channelSetAuto(self, url, auto=True):
        pass

    def makrAsDownloaded(self, channel, title, date, filename):
        sql = """UPDATE videos
                    SET filename = ?,
                        status = 'downloaded'
                    WHERE channel_url = ? and
                          title = ? and
                          date = ?"""
        self.cursor.execute(sql, (filename, channel, title, date))
        self.conn.commit()


class ItemList():
    def __init__(self, items, db):
        self.items = items
        self.db = db

    def update(self, items=None):
        if None == items:
            items = self.db.selectVideos()
        self.items = items

    def add(self, item):
        self.items.append(item)
        self.updateStrings()

    def download(self, idx):
        item = self.items[idx]
        link = item['link']
        # Set filename # TODO handle collision add into db even before downloading
        channel = db.getChannel(item['url'])
        path = strToFilename(channel['title'])
        if not os.path.exists(path):
            os.makedirs(path)

        if 'rss' == channel['type']:
            ext = link.split('.')[-1]
            filename = "%s/%s_%s.%s" % (path, tsToDate(item['date']),
                    strToFilename(item['title']), ext)

            # Download file TODO background
            printInfos("Download "+link)
            urllib.request.urlretrieve(link, filename)

        elif 'yt' == channel['type']:
            pass

        # Change status and filename
        self.db.makrAsDownloaded(item['url'], item['title'],
                item['date'], filename)
        item['filename'] = filename
        item['status'] = 'downloaded'

    def getItems(self, status):
        return [ v for v in self.items if v['status'] == status ]


class Rss:
    @classmethod
    def getData(clss, url):
        rss = fp.parse(url)

        feed = rss.feed
        if not len(feed):
            printInfos('Cannot load '+url)
            return None

        data = {}
        data['url'] = url
        data['title'] = feed['title']
        data['updated'] = mktime(feed['updated_parsed'])

        data['items'] = []
        entries = rss.entries
        for entry in entries:
            title = entry['title']
            date = int(mktime(entry['published_parsed']))
            link = list(map(lambda x: x['href'], entry['links']))[1]
            if 'itunes_duration' in entry:
                sduration = entry['itunes_duration']
                duration = sum([ int(x)*60**i for (i, x) in
                    enumerate(sduration.split(':')[::-1]) ])
            else:
                duration = -1
            data['items'].append({'channel':url, 'title':title , 'date':date,
                'link':link , 'duration':duration})
        return data

    @classmethod
    def addChannel(clss, db, area, url, auto=False, genre=None):
        # Check not already present in db
        channel = db.getChannel(url)
        if None != channel:
            return '"%s" already present' % channel['title']

        # Retrieve url feed
        data = clss.getData(url)

        # Add channel to db
        db.addChannel(url, data['title'], 'rss', genre, auto, data)

        # Update video list
        clss.saveVideoUpdates(db, data)

        if area:
            area.updateItems(db.selectVideos())

        return data['title']+' added'

    @classmethod
    def updateVideos(clss, db, urls=None):
        updated = False
        if None == urls:
            urls = list(map(lambda x: x['url'], db.selectChannels()))
        for url in urls:
            data = clss.getData(url)
            if data:
                updated = updated or clss.saveVideoUpdates(db, data)
        return updated

    @classmethod
    def saveVideoUpdates(clss, db, data):
        return db.addVideos(data)


class TextArea:
    def __init__(self, screen, itemList, status):
        height, width = screen.getmaxyx()
        self.height = height-2
        self.width = width-1
        self.itemList = itemList
        self.status = status
        self.win = curses.newwin(self.height+1, self.width, 1, 0)
        self.win.bkgd(curses.color_pair(2))
        self.win.keypad(1) # to handle special keys as one key
        self.highlightOn = False
        self.highlightString = None
        self.oldCursor = 0
        self.cursor = 0
        self.firstLine = 0

        self.setContent(False)

    def getIdx(self):
        return self.firstLine+self.cursor

    def getCurrentLine(self):
        return self.content[self.firstLine+self.cursor]

    def highlight(self, string):
        self.highlightOn = True
        self.highlightString = string
        self.display(redraw=True)
        self.nextHighlight()

    def toString(self, item):
        date = tsToDate(item['date'])
        duration = str(timedelta(seconds=item['duration']))
        separator = u" \u2022 "
        lastSeparator = " "

        string = date
        string += separator
        string += item['channel']
        string += separator
        string += item['title']

        space = self.width-1-len(string+lastSeparator+duration)
        if space < 0:
            string = string[:space-3]
            string += '...'
        else:
            string += ' '*space

        string += lastSeparator
        string += duration

        return string

    def setContent(self, redraw=True):
        newItems = self.itemList.getItems(self.status)
        self.content = list(map(self.toString, newItems))
        self.forceRedraw()

    def nextHighlight(self):
        itemIdx = None
        for i in range(self.firstLine+self.cursor+1, len(self.content)):
            if self.highlightString in self.content[i]:
                itemIdx = i
                break
        printInfos(itemIdx)
        if itemIdx:
            self.moveCursor(itemIdx)

    def noHighlight(self):
        self.highlightOn = False
        self.display(redraw=True)

    def moveCursor(self, itemIdx):
        self.moveScreen('line', 'down', itemIdx-self.cursor-self.firstLine)

    def updateItems(self, items):
        self.itemList.update(items)
        self.setContent()

    def printLine(self, line, string, bold=False):
        normalStyle = curses.color_pair(2)
        boldStyle = curses.color_pair(1)
        highlightStyle = curses.color_pair(4)
        self.win.move(line, 0)
        self.win.clrtoeol()
        style = None
        if bold:
            self.win.addstr(line, 0, string, boldStyle)
        else:
            if self.highlightOn:
                styles = (normalStyle, highlightStyle)

                # Split with highlight string and put it back
                parts = string.split(self.highlightString)
                missingStrings = [self.highlightString]*len(parts)
                parts = [val for pair in zip(parts, missingStrings)
                        for val in pair][:-1]

                written = 0
                styleIdx = 0
                for part in parts:
                    self.win.addstr(line, written, part, styles[styleIdx])
                    written += len(part)
                    styleIdx = (styleIdx+1)%2
            else:
                self.win.addstr(line, 0, string, normalStyle)

    def moveScreen(self, what, way, number=1):
        redraw = False
        # Move one line down
        if what == 'line' and way == 'down':
            self.oldCursor = self.cursor
            # More lines below
            if self.firstLine+self.cursor+number < len(self.content):
                self.cursor += number
        # Move one line up
        elif what == 'line' and way == 'up':
            self.oldCursor = self.cursor
            # More lines above
            if self.firstLine+self.cursor-number >= 0:
                self.cursor -= number
        # Move one page down
        elif what == 'page' and way == 'down':
            self.oldCursor = self.cursor
            self.cursor = min(self.cursor+self.height*number, len(self.content)-1)
            printInfos(str(self.cursor))
        # Move one page up
        elif what == 'page' and way == 'up':
            self.oldCursor = self.cursor
            self.cursor -= self.height*number
            printInfos(str(self.cursor))
        elif what == 'all' and way == 'up':
            self.oldCursor = self.cursor
            self.cursor = -self.firstLine
        elif what == 'all' and way == 'down':
            self.oldCursor = self.cursor
            self.cursor = len(self.content)-1-self.firstLine
            printInfos(str(self.cursor))

        # If cursor moved
        if self.cursor != self.oldCursor:
            if self.cursor < 0 and self.firstLine == 0:
                self.cursor = 0
            if self.cursor >= self.height or self.cursor < 0:
                redraw = True
                self.firstLine = int((self.cursor+self.firstLine)/self.height)*self.height
                self.cursor %= self.height

        self.display(redraw)

    def forceRedraw(self):
        self.oldCursor = 0
        self.cursor = 0
        self.firstLine = 0
        self.display(True)

    def display(self, redraw=False):
        # We draw all the page (shift)
        if redraw == True:
            self.win.erase()
            lastLine = min(self.firstLine+self.height, len(self.content))
            lineNumber = 0
            for line in self.content[self.firstLine:lastLine]:
                # Line where cursor is, bold
                if lineNumber == self.cursor:
                    self.printLine(lineNumber, line, True)
                else:
                    self.printLine(lineNumber, line)
                lineNumber += 1
            # Erase previous text for empty lines (bottom of scroll)
            for lineNumber in range(lineNumber, self.height):
                self.win.move(lineNumber, 0)
                self.win.clrtoeol()

        elif self.oldCursor != self.cursor:
            self.printLine(self.oldCursor, self.content[self.firstLine+self.oldCursor])
            self.printLine(self.cursor, self.content[self.firstLine+self.cursor], True)
        self.win.refresh()

class TitleArea:
    def __init__(self, screen, title):
        height, width = screen.getmaxyx()
        self.height = 1
        self.width = width-1
        self.win = curses.newwin(self.height, self.width, 0, 0)
        self.win.bkgd(curses.color_pair(3))
        self.win.keypad(1)
        self.print(title)

    def print(self, string):
        self.win.move(0, 0)
        self.win.clrtoeol()
        self.win.addstr(0, 0, str(string))
        self.win.refresh()

class StatusArea:
    def __init__(self, screen):
        height, width = screen.getmaxyx()
        self.height = 1
        self.width = width-1
        self.win = curses.newwin(self.height, self.width, height-1, 0)
        self.win.bkgd(curses.color_pair(3))
        self.win.keypad(1)
        self.print('')

    def print(self, string):
        self.win.move(0, 0)
        self.win.clrtoeol()
        self.win.addstr(0, 0, str(string))
        self.win.refresh()

    def runCommand(self, prefix):
        self.print(prefix)
        #curses.curs_set(2)
        tb = curses.textpad.Textbox(self.win)
        string = tb.edit()[len(prefix):-1] # remove ':' and last char
        return string


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

tabs = []
tabnames = []

itemList = ItemList(db.selectVideos(), db)

# New tab
tabs.append(TextArea(screen, itemList, 'new'))
newStr = 'New feeds'
tabnames.append(newStr)

# Play tab
tabs.append(TextArea(screen, itemList, 'downloaded'))
playStr = 'Play'
tabnames.append(playStr)

curTab = 0
tab = tabs[curTab]
tab.display(True)

titleArea = TitleArea(screen, tabnames[curTab])
statusArea = StatusArea(screen)

updatedContent = False
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
                msg = Rss.addChannel(db, tab, *command[1:])
                printInfos(msg)


    elif key == ord('q'):
        break
    elif key == ord('\n'):
        tab.itemList.download(idx)
        tab.setContent(True)
        updatedContent = True
    elif key == ord('u'):
        printInfos('Update...')
        updated = Rss.updateVideos(db)
        if updated:
            tab.updateItems(db.selectVideos())
            updatedContent = True

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
        curTab = (curTab+1)%len(tabs)
        tab = tabs[curTab]
        titleArea.print(tabnames[curTab])
        if updatedContent:
            updatedContent = False
            tab.setContent(True)
        else:
            tab.display(True)
