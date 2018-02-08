from datetime import datetime, timedelta
import unicodedata

from config import logPath

def printableStr(string):
    newStr = ''

    for c in string:
        # For zero-width characters
        if unicodedata.category(c)[0] in ('M', 'C'):
            continue

        w = unicodedata.east_asian_width(c)
        if w in ('N', 'Na', 'H', 'A'):
            newStr += c
        else:
            newStr += '🖥'

    return newStr

def printLog(string):
    if printLog.reset:
        mode = 'w'
        printLog.reset = False
    else:
        mode = 'a'
    filename = logPath
    with open(filename, mode) as myfile:
        myfile.write(str(string)+"\n")
printLog.reset = True

def tsToDate(ts):
    return datetime.fromtimestamp(int(ts)).strftime('%Y-%m-%d')

def strToFilename(string):
    return unicodedata.normalize('NFKD', string).encode('ascii', 'ignore')\
            .decode('ascii').replace(' ', '-').replace('/', '-')

def durationToStr(duration):
    if duration < 0: duration = 0
    return str(timedelta(seconds=duration))

# Truncate the line or add spaces if needed
# When !truncate list is returned for each line
def formatString(string, width, truncate=True):

    # If line is too long
    if truncate:
        space = width-len(string)
        if 0 > space:
            return string[:space-1]+'…'
        else:
            return string+' '*space

    else:
        strings = []
        stringList = string.split(' ')
        while len(stringList):
            line = ''
            remain = width
            # We fill in the line
            while len(stringList) and len(stringList[0]) <= remain:
                s = stringList.pop(0)
                line += s+' '
                remain -= len(s)+1

            # Check we got someting to put
            if not len(line): # line was too long to be nicely cut
                line = stringList[0][:width]
                stringList[0] = stringList[0][width:]
                strings.append(line)
            else:
                line = line[:-1] # remove last ' '
                remain += 1
                strings.append(line+' '*remain)

        return strings
