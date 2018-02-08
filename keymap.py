import curses

class Keymap():
    def __init__(self, config):
        from config import keys
        self.keymaps = self.loadKeymap(keys)

        self.keys = {}
        for m in self.keymaps:
            self.addKey(*m)

    def addKey(self, areaType, key, action):
        self.keys[(areaType, key)] = action

    def getAction(self, areaType, key):
        subType = areaType.split('_')[0]
        for t in (areaType, subType, ''):
            if (t, key) in self.keys:
                return self.keys[(t, key)]
        return None

    def mapToHelp(self, areaType):
        elements = []
        maxLen = 0
        for m in self.keymaps:
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

    def loadKeymap(self, keys):
        keymaps = []
        rawKeymap = keys
        for action, value in rawKeymap.items():
            where = value[:value.index(':')]
            key = value[value.index(':')+1:]

            try:
                key = int(key)
            except ValueError:
                key = key[1:-1]
                key = bytes(key, "utf-8").decode("unicode_escape")
                key = ord(key)

            keymaps.append((where, key, action))

        return keymaps


defaultKeymaps = [
        ('', 'j', 'line_down'),
        ('', 'k', 'line_up'),
        ('', 6, 'page_down'), # ctrl-f
        ('', 2, 'page_up'), # ctrl-b
        ('', 'g', 'top'),
        ('', 'G', 'bottom'),
        ('', '\t', 'tab_next'),
        ('', 90, 'tab_prev'), # shift-tab
        ('', '?', 'help'),

        ('', 18, 'redraw'), # Ctrl-r
        ('', 7, 'screen_infos'), # Ctrl-g

        ('', ':', 'command_get'),
        ('', '/', 'search_get'),
        ('', 'n', 'search_next'),
        ('', 'N', 'search_prev'),

        ('', 'q', 'quit'),

        ('', ' ', 'select_item'),
        ('', '$', 'select_until'),
        ('', '^', 'select_clear'),

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
