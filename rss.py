import feedparser as fp
from time import mktime, time
from utils import printLog, printableStr
import urllib.request


def getData(url, printInfos=print):
    rss = fp.parse(url)

    feed = rss.feed
    if not len(feed):
        printInfos('Cannot load '+url)
        return None

    data = {}
    data['url'] = url
    data['title'] = printableStr(feed['title'])
    data['type'] = 'rss'

    data['items'] = []
    entries = rss.entries
    maxtime = 0
    for entry in entries:
        video = {}
        video['channel'] = data['title']
        video['url'] = url
        video['title'] = printableStr(entry['title'])
        video['date'] = int(mktime(entry['published_parsed']))
        maxtime = max(maxtime, video['date'])

        video['link'] = None
        video['linkType'] = None # TODO add in database
        for link in entry['links']:
            if 'video' in link['type'] or 'audio' in link['type']:
                video['link'] = link['href']
                video['linkType'] = link['type']

        if 'itunes_duration' in entry:
            sduration = entry['itunes_duration']
            video['duration'] = sum([ int(x)*60**i for (i, x) in
                enumerate(sduration.split(':')[::-1]) ])
        data['items'].append(video)

    if 'updated_parsed' in feed:
        data['updated'] = mktime(feed['updated_parsed'])
    else:
        data['updated'] = maxtime

    return data

def download(url, filename, printInfos=print):
    try:
        urllib.request.urlretrieve(url, filename)
    except urllib.error.URLError:
        printInfos('Cannot access to %s' % url)
        return 1
    else:
        return 0
