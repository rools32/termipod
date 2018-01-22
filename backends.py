import os, os.path

import rss
import yt

def getData(url, printInfos=print, new=False):
    if 'youtube' in url:
        data = yt.getData(url, printInfos, new)
    else:
        data = rss.getData(url, printInfos)
    return data

def download(item, channel, printInfos=print):
    link = item['link']

    # Set filename # TODO handle collision add into db even before downloading
    path = strToFilename(channel['title'])
    if not os.path.exists(path):
        os.makedirs(path)

    # Download file TODO background
    printInfos("Download "+link)
    if 'rss' == channel['type']:
        ext = link.split('.')[-1]
        filename = "%s/%s_%s.%s" % (path, tsToDate(item['date']),
                strToFilename(item['title']), ext)
        rss.download(link, filename)

    elif 'youtube' == channel['type']:
        filename = "%s/%s_%s.%s" % (path, tsToDate(item['date']),
                strToFilename(item['title']), 'mp4')
        yt.download(link, filename)

    # Change status and filename
    item['filename'] = filename
    item['status'] = 'downloaded'
