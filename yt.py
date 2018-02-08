import feedparser as fp
import youtube_dl
import re
from datetime import datetime
from time import mktime, time
from utils import printLog, printableStr

class DownloadLogger(object):
    def __init__(self, printInfos, url):
        self.printInfos = printInfos
        self.url = url
        self.step = 0

    def debug(self, msg):
        regex = '.*\[download\] *([0-9.]*)% of *[0-9.]*.iB '+ \
                'at *[0-9.]*.iB/s ETA ([0-9:]*)'
        match = re.match(regex, msg)
        if None != match:
            percentage = int(float(match.groups()[0]))
            eta = match.groups()[1]
            if percentage >= self.step:
                self.printInfos('Downloading %s (%d%% ETA %s)...' % \
                        (self.url, percentage, eta))
                self.step = int(percentage/10+1)*10

    def warning(self, msg):
        self.printInfos('[YTDL warning] %s' % msg)

    def error(self, msg):
        self.printInfos('[YTDL error] %s' % msg)

class DataLogger(object):
    def __init__(self, printInfos, url):
        self.printInfos = printInfos
        self.url = url

    def debug(self, msg):
        regex="\[download\] Downloading video (\d*) of (\d*)"
        match = re.match(regex, msg)
        if None != match:
            current = float(match.groups()[0])
            total = float(match.groups()[1])
            self.printInfos('Adding %s (%d%%)' % \
                    (self.url, int(current*100/total)))

    def warning(self, msg):
        self.printInfos('[YTDL warning] %s' % msg)

    def error(self, msg):
        self.printInfos('[YTDL error] %s' % msg)

def download(url, filename, printInfos=print):
    ydl_opts = {'logger': DownloadLogger(printInfos, url),
            'outtmpl': filename, 'format': 'mp4'}
    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        try:
            return ydl.download([url])
        except:
            return 1

def getData(url, printInfos=print, new=False):
    # If first add, we use ytdl to get old media
    if new:
        ydl_opts = {'logger': DataLogger(printInfos, url), 'ignoreerrors': True}
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info( url, download=False)
        if None == result or None == result['entries']:
            printInfos("Cannot get data from %s" % url)
            return None

        entries = result['entries']

        # Find channel name
        channel_title = None
        for entry in entries:
            if None != entry:
                channel_title = printableStr(entry['uploader'])
                break

        if None == channel_title:
            return None

        data = {}
        data['url'] = url
        data['title'] = channel_title
        data['updated'] = int(time())
        data['type'] = 'youtube'

        data['items'] = []
        for entry in entries:
            if None == entry :
                continue
            medium = {}
            medium['channel'] = data['title']
            medium['url'] = url
            medium['title'] = printableStr(entry['title'])
            medium['date'] = int(mktime(datetime.strptime(
                entry['upload_date'], "%Y%m%d").timetuple()))
            medium['description'] = entry['description']
            medium['link'] = entry['webpage_url']
            medium['duration'] = entry['duration']
            data['items'].append(medium)

        return data

    else:
        feedUrl = url.replace('channel/', 'feeds/videos.xml?channel_id=')
        rss = fp.parse(feedUrl)

        feed = rss.feed
        if not len(feed):
            printInfos('Cannot load '+feedUrl)
            return None

        data = {}
        data['url'] = url
        data['title'] = printableStr(feed['title'])
        data['updated'] = mktime(feed['published_parsed'])
        data['type'] = 'youtube'

        data['items'] = []
        entries = rss.entries
        for entry in entries:
            medium = {}
            medium['channel'] = data['title']
            medium['url'] = url
            medium['title'] = printableStr(entry['title'])
            medium['date'] = int(mktime(entry['published_parsed']))
            medium['description'] = entry['description']
            medium['link'] = entry['link']
            data['items'].append(medium)

        return data

