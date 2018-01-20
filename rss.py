import feedparser as fp
from time import mktime
from utils import printLog

def getData(url):
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

def addChannel(db, itemList, url, auto=False, genre=None):
    # Check not already present in db
    channel = db.getChannel(url)
    if None != channel:
        return '"%s" already present' % channel['title']

    # Retrieve url feed
    data = getData(url)

    # Add channel to db
    db.addChannel(url, data['title'], 'rss', genre, auto, data)

    # Update video list
    saveVideoUpdates(db, data)

    if itemList:
        itemList.update(db.selectVideos())

    return data['title']+' added'

def updateVideos(db, urls=None):
    updated = False
    if None == urls:
        urls = list(map(lambda x: x['url'], db.selectChannels()))
    for url in urls:
        data = getData(url)
        if data:
            updated = updated or saveVideoUpdates(db, data)
    return updated

def saveVideoUpdates(db, data):
    return db.addVideos(data)


