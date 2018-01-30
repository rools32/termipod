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
    return str(timedelta(seconds=duration))


