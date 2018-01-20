import curses
import curses.textpad

from utils import durationToStr, tsToDate

class TextArea:
    def __init__(self, screen, itemList, status, printInfos):
        self.printInfos = printInfos
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
        duration = durationToStr(item['duration'])
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
        self.printInfos(itemIdx)
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
            self.printInfos(str(self.cursor))
        # Move one page up
        elif what == 'page' and way == 'up':
            self.oldCursor = self.cursor
            self.cursor -= self.height*number
            self.printInfos(str(self.cursor))
        elif what == 'all' and way == 'up':
            self.oldCursor = self.cursor
            self.cursor = -self.firstLine
        elif what == 'all' and way == 'down':
            self.oldCursor = self.cursor
            self.cursor = len(self.content)-1-self.firstLine
            self.printInfos(str(self.cursor))

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


