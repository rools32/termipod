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
        medium = {}
        medium['channel'] = data['title']
        medium['url'] = url
        medium['title'] = printableStr(entry['title'])
        medium['date'] = int(mktime(entry['published_parsed']))
        medium['description'] = entry['summary']
        maxtime = max(maxtime, medium['date'])

        medium['link'] = None
        medium['linkType'] = None # TODO add in database
        for link in entry['links']:
            if 'medium' in link['type'] or 'audio' in link['type']:
                medium['link'] = link['href']
                medium['linkType'] = link['type']

        if 'itunes_duration' in entry:
            sduration = entry['itunes_duration']
            medium['duration'] = sum([ int(x)*60**i for (i, x) in
                enumerate(sduration.split(':')[::-1]) ])
        data['items'].append(medium)

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
