import curses

def getKeyName(screen):
    key = screen.getch()
    keyName = curses.keyname(key).decode()
    if ' ' == keyName:
        keyName = 'KEY_SPACE'
    elif '^J' == keyName:
        keyName = '\n'
    elif '^I' == keyName:
        keyName = '\t'
    return keyName

class Keymap():
    def __init__(self, config):
        from config import keys
        self.keymaps = self.loadKeymap(keys)

        self.keys = {}
        for m in self.keymaps:
            self.addKey(*m)

    def addKey(self, areaType, key, action):
        self.keys[(areaType, key)] = action

    def getAction(self, areaType, keyName):
        subType = areaType.split('_')[0]
        for t in (areaType, subType, ''):
            if (t, keyName) in self.keys:
                return self.keys[(t, keyName)]
        return None

    def mapToHelp(self, areaType):
        maxLen = 0
        keys = {} # indexed by action
        for where, key, action in self.keymaps:
            if where in areaType:
                keyseq = key.encode('unicode_escape').decode('ASCII')

                if action in keys:
                    keys[action] += ', '+keyseq
                else:
                    keys[action] = keyseq
                maxLen = max(maxLen, len(keys[action]))

        lines = []
        for action, keyList in keys.items():
            numSpaces = maxLen-len(keyList)+1
            lines.append('%s%s%s' % \
                    (keyList, ' '*numSpaces, descriptions[action]))

        return lines

    def loadKeymap(self, keys):
        keymaps = []
        rawKeymap = keys
        for action, values in rawKeymap.items():
            for value in values.split(' '):
                where = value[:value.index('/')]
                if '*' == where:
                    where = ''

                key = value[value.index('/')+1:]
                key = bytes(key, "utf-8").decode("unicode_escape")
                keymaps.append((where, key, action))

        return keymaps


defaultKeymaps = [
        ('*', 'j', 'line_down'),
        ('*', 'KEY_DOWN', 'line_down'),
        ('*', 'k', 'line_up'),
        ('*', 'KEY_UP', 'line_up'),
        ('*', '^F', 'page_down'),
        ('*', 'KEY_NPAGE', 'page_down'),
        ('*', '^B', 'page_up'),
        ('*', 'KEY_PPAGE', 'page_up'),
        ('*', 'g', 'top'),
        ('*', 'KEY_HOME', 'top'),
        ('*', 'G', 'bottom'),
        ('*', 'KEY_END', 'bottom'),
        ('*', '\t', 'tab_next'),
        ('*', 'KEY_BTAB', 'tab_prev'), # shift-tab
        ('*', '?', 'help'),

        ('*', '^R', 'redraw'),
        ('*', '^L', 'refresh'),
        ('*', '^G', 'screen_infos'),

        ('*', ':', 'command_get'),
        ('*', '/', 'search_get'),
        ('*', 'n', 'search_next'),
        ('*', 'N', 'search_prev'),

        ('*', 'q', 'quit'),

        ('*', 'KEY_SPACE', 'select_item'),
        ('*', '$', 'select_until'),
        ('*', '^', 'select_clear'),

        ('media', '*', 'search_channel'),
        ('media', 'l', 'medium_play'),
        ('media', 'a', 'medium_playadd'),
        ('media', 'h', 'medium_stop'),
        ('media', 'd', 'medium_remove'),
        ('media', 'r', 'medium_read'),
        ('media', 'R', 'medium_skip'),
        ('media', 'c', 'channel_filter'),
        ('media', 's', 'state_filter'),
        ('media', 'i', 'infos'), # TODO for channels too (s/'media'/'')
        ('media', 'I', 'description'), # TODO for channels too (s/'media'/'')

        ('media_remote', '\n', 'medium_download'),
        ('media_remote', 'u', 'medium_update'),

        ('media_local', '\n', 'medium_playadd'),

        ('channels', 'a', 'channel_auto'),
        ('channels', 'A', 'channel_auto_custom'),
        ('channels', '\n', 'channel_show_media'),
    ]

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

        'redraw': 'Redraw all screen',
        'refresh': 'Reinit current area',

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
        'medium_read': 'Mark as read',
        'medium_skip': 'Mark as skipped',
        'channel_filter': 'Filter same channel',
        'state_filter': 'Show next state  panel',
        'infos': 'Show information',
        'description': 'Show description',

        'medium_download': 'Download media',
        'medium_update': 'Update media list',

        'channel_auto': 'Set channel as auto',
        'channel_auto_custom': 'Set custom value for auto',
        'channel_show_media': 'Show media of channel',
}
