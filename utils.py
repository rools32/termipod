from datetime import datetime, timedelta
import unicodedata

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

def durationToStr(duration):
    return str(timedelta(seconds=duration))


