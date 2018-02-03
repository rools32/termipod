from datetime import datetime, timedelta
import unicodedata
import config

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
    filename = config.logFile
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
    space = width-len(string)

    # If line is too long
    if truncate:
        if 0 > space:
            return string[:space-1]+'…'
        else:
            return string+' '*space

    else:
        strings = []
        while 0 > space:
            strings.append(string[:space])
            string = string[space:]
            space = width-len(string)

        if 0 <= space:
            strings.append(string+' '*space)

        return strings
