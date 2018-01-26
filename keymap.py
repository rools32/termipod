keys = {}

def addKey(areaType, key, action):
    keys[(areaType, key)] = action

def getAction(areaType, key):
    subType = areaType.split('_')[0]
    for t in (areaType, subType, ''):
        if (t, key) in keys:
            return keys[(t, key)]
    return None

maps = [
    ('', ord('j'), 'line_down'),
    ('', ord('k'), 'line_up'),
    ('', 6, 'page_down'),
    ('', 2, 'page_up'),
    ('', ord('g'), 'top'),
    ('', ord('G'), 'bottom'),
    ('', ord('\t'), 'tab_next'),

    ('', ord(':'), 'command_get'),
    ('', ord('/'), 'search_get'),
    ('', ord('n'), 'search_next'),

    ('', ord('q'), 'quit'),

    ('videos', ord('*'), 'search_channel'),
    ('videos', ord('l'), 'video_play'),
    ('videos', ord('a'), 'video_playadd'),
    ('videos', ord('h'), 'video_stop'),

    ('videos_remote', ord('\n'), 'video_download'),
    ('videos_remote', ord('u'), 'video_update'),
]

for m in maps:
    addKey(*m)
