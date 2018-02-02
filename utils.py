from datetime import datetime, timedelta
import unicodedata

def printLog(string):
    if printLog.reset:
        mode = 'w'
        printLog.reset = False
    else:
        mode = 'a'
    filename = 'log.txt'
    with open(filename, mode) as myfile:
        myfile.write(str(string)+"\n")
printLog.reset = True

def tsToDate(ts):
    return datetime.fromtimestamp(int(ts)).strftime('%Y-%m-%d')

def strToFilename(string):
    return unicodedata.normalize('NFKD', string).encode('ascii', 'ignore')\
            .decode('ascii').replace(' ', '-')

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
            return string[:space-3]+'...'
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
