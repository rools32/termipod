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
        helpStr = descriptions[e[1]]
        length = len(e[0])
        numSpaces = maxLen-length+1
        lines.append('<%s>%s%s' % (e[0], ' '*numSpaces, helpStr))

    return lines

descriptions = {
        'line_down': 'Go one line down',
        'line_up': 'Go one line up',
        'page_down': 'Go one page down',
        'page_up': 'Go one page up',
        'top': 'Go top',
        'bottom': 'Go bottom',
        'tab_next': 'Go next tab',
        'tab_prev': 'Go previous tab',
        'help': 'Show help',

        'screen_infos': 'Show screen information',

        'command_get': 'Command input',
        'search_get': 'Search pattern',
        'search_next': 'Move to next search pattern',
        'search_prev': 'Move to previous search pattern',

        'quit': 'Quit',

        'select_item': 'Select item',
        'select_until': 'Grow selection',
        'select_clear': 'Clear selection',

        'search_channel': 'Highlight channel',
        'medium_play': 'Play media',
        'medium_playadd': 'Enqueue media',
        'medium_stop': 'Stop playing',
        'medium_remove': 'Remove media',
        'medium_read': 'Makr as read',
        'medium_skip': 'Makr as skipped',
        'channel_filter': 'Filter same channel',
        'state_filter': 'Show next state  panel',
        'infos': 'Show information',

        'medium_download': 'Download media',
        'medium_update': 'Update media list',

        'channel_auto': 'Set channel as auto',
        'channel_auto_custom': 'Set custom value for auto',
        'channel_show_media': 'Show media of channel',
    }

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

    ('media', ord('*'), 'search_channel'),
    ('media', ord('l'), 'medium_play'),
    ('media', ord('a'), 'medium_playadd'),
    ('media', ord('h'), 'medium_stop'),
    ('media', ord('d'), 'medium_remove'),
    ('media', ord('r'), 'medium_read'),
    ('media', ord('R'), 'medium_skip'),
    ('media', ord('c'), 'channel_filter'),
    ('media', ord('s'), 'state_filter'),
    ('media', ord('i'), 'infos'), # TODO for channels too (s/'media'/'')

    ('media_remote', ord('\n'), 'medium_download'),
    ('media_remote', ord('u'), 'medium_update'),

    ('channels', ord('a'), 'channel_auto'),
    ('channels', ord('A'), 'channel_auto_custom'),
    ('channels', ord('\n'), 'channel_show_media'),
]

for m in keymaps:
    addKey(*m)
