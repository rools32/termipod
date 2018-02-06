from utils import printLog
import curses

keys = {}

def addKey(areaType, key, action):
    keys[(areaType, key)] = action

def getAction(areaType, key):
    subType = areaType.split('_')[0]
    for t in (areaType, subType, ''):
        if (t, key) in keys:
            return keys[(t, key)]
    return None

def mapToHelp(areaType):
    elements = []
    maxLen = 0
    for m in keymaps:
        if m[0] in areaType:
            keyseq = curses.keyname(m[1]).decode("utf-8")
            if '^J' == keyseq:
                keyseq = 'Return'
            elif ' ' == keyseq:
                keyseq = 'Space'
            elif '^I' == keyseq:
                keyseq = 'Tab'
            elements.append((keyseq, m[2]))
            maxLen = max(maxLen, len(keyseq))

    lines = []
    for e in elements:
        length = len(e[0])
        numSpaces = maxLen-length+1
        lines.append('<%s>%s%s' % (e[0], ' '*numSpaces, e[1]))

    return lines

keymaps = [
    ('', ord('j'), 'line_down'),
    ('', ord('k'), 'line_up'),
    ('', 6, 'page_down'),
    ('', 2, 'page_up'),
    ('', ord('g'), 'top'),
    ('', ord('G'), 'bottom'),
    ('', ord('\t'), 'tab_next'),
    ('', 90, 'tab_prev'),
    ('', ord('?'), 'help'),

    ('', 7, 'screen_infos'),

    ('', ord(':'), 'command_get'),
    ('', ord('/'), 'search_get'),
    ('', ord('n'), 'search_next'),
    ('', ord('N'), 'search_prev'),

    ('', ord('q'), 'quit'),

    ('', ord(' '), 'select_item'),
    ('', ord('$'), 'select_until'),
    ('', ord('^'), 'select_clear'),

    ('videos', ord('*'), 'search_channel'),
    ('videos', ord('l'), 'video_play'),
    ('videos', ord('a'), 'video_playadd'),
    ('videos', ord('h'), 'video_stop'),
    ('videos', ord('d'), 'video_remove'),
    ('videos', ord('r'), 'video_read'),
    ('videos', ord('R'), 'video_skip'),
    ('videos', ord('c'), 'channel_filter'),
    ('videos', ord('s'), 'state_filter'),
    ('videos', ord('i'), 'infos'), # TODO for channels too (s/'videos'/'')

    ('videos_remote', ord('\n'), 'video_download'),
    ('videos_remote', ord('u'), 'video_update'),

    ('channels', ord('a'), 'channel_auto'),
    ('channels', ord('A'), 'channel_auto_custom'),
    ('channels', ord('\n'), 'channel_show_videos'),
]

for m in keymaps:
    addKey(*m)
