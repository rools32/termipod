import feedparser as fp
from time import mktime, time
from utils import printLog
import urllib.request


def getData(url, printInfos=print):
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
        video['status'] = 'new'
        video['filename'] = ''
        video['tags'] = ''
        data['items'].append(video)
    return data

def download(url, filename):
    urllib.request.urlretrieve(url, filename)
