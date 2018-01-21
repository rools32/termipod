import feedparser as fp
from time import mktime, time
from datetime import datetime
from os import devnull
from utils import printLog
import youtube_dl
from contextlib import redirect_stdout, redirect_stderr


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
    data['type'] = 'rss'

    data['items'] = []
    entries = rss.entries
    for entry in entries:
        video = {}
        video['channel'] = url
        video['title'] = entry['title']
        video['date'] = int(mktime(entry['published_parsed']))
        video['link'] = list(map(lambda x: x['href'], entry['links']))[1]
        if 'itunes_duration' in entry:
            sduration = entry['itunes_duration']
            video['duration'] = sum([ int(x)*60**i for (i, x) in
                enumerate(sduration.split(':')[::-1]) ])
        else:
            video['duration'] = -1
        data['items'].append(video)
    return data

def getYTData(url, new=False):
    # If first add, we use ytdl to get old videos
    if new:
        with open(devnull, 'w') as f:
            with redirect_stdout(f), redirect_stderr(f):
                ydl = youtube_dl.YoutubeDL({'ignoreerrors': True})
                with ydl:
                    result = ydl.extract_info( url, download=False)
        entries = result['entries']

        data = {}
        data['url'] = url
        data['title'] = channel_title = entries[0]['uploader']
        data['updated'] = int(time())
        data['type'] = 'youtube'

        data['items'] = []
        for entry in entries:
            if None == entry :
                continue
            video = {}
            video['channel'] = url
            video['title'] = entry['title']
            video['date'] = int(mktime(datetime.strptime(
                entry['upload_date'], "%Y%m%d").timetuple()))
            video['link'] = entry['webpage_url']
            video['duration'] = entry['duration']
            data['items'].append(video)

        return data

    else:
        feedUrl = url.replace('channel/', 'feeds/videos.xml?channel_id=')
        # TODO
        rss = fp.parse(feedUrl)

        feed = rss.feed
        if not len(feed):
            printInfos('Cannot load '+feedUrl)
            return None

        data = {}
        data['url'] = url
        data['title'] = feed['title']
        data['updated'] = mktime(feed['published_parsed'])
        data['type'] = 'youtube'

        data['items'] = []
        entries = rss.entries
        for entry in entries:
            video = {}
            video['channel'] = url
            video['title'] = entry['title']
            video['date'] = int(mktime(entry['published_parsed']))
            video['link'] = entry['link']
            video['duration'] = -1
            data['items'].append(video)

        return data

def addChannel(db, itemList, url, auto=False, genre=None):
    # Check not already present in db
    channel = db.getChannel(url)
    if None != channel:
        return '"%s" already present' % channel['title']

    # Retrieve url feed
    if 'youtube' in url:
        data = getYTData(url, True)
    else:
        data = getData(url)

    # Add channel to db
    db.addChannel(url, data['title'], data['type'], genre, auto, data)

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
        channel = db.getChannel(url)
        if 'youtube' == channel['type']:
            data = getYTData(url)
        elif 'rss' == channel['type']:
            data = getData(url)

        if data:
            updated = updated or saveVideoUpdates(db, data)
    return updated

def saveVideoUpdates(db, data):
    return db.addVideos(data)


