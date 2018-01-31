import feedparser as fp
import youtube_dl
from datetime import datetime
from time import mktime, time
from utils import printLog

class Logger(object):
    def debug(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        pass

def download(url, filename, printInfos=print):
    ydl_opts = {'logger': Logger(), 'outtmpl': filename, 'format': 'mp4'}
    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        return ydl.download([url])

def getData(url, printInfos=print, new=False):
    # If first add, we use ytdl to get old videos
    if new:
        ydl_opts = {'logger': Logger(), 'ignoreerrors': True}
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info( url, download=False)
        if None == result:
            printInfos("Cannot get data from %s" % url)
            return None

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
            video['channel'] = data['title']
            video['url'] = url
            video['title'] = entry['title']
            video['date'] = int(mktime(datetime.strptime(
                entry['upload_date'], "%Y%m%d").timetuple()))
            video['link'] = entry['webpage_url']
            video['duration'] = entry['duration']
            data['items'].append(video)

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
        data['title'] = feed['title']
        data['updated'] = mktime(feed['published_parsed'])
        data['type'] = 'youtube'

        data['items'] = []
        entries = rss.entries
        for entry in entries:
            video = {}
            video['channel'] = data['title']
            video['url'] = url
            video['title'] = entry['title']
            video['date'] = int(mktime(entry['published_parsed']))
            video['link'] = entry['link']
            data['items'].append(video)

        return data

