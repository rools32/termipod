import mpv
from utils import *

class Player():
    def __init__(self, itemList, printInfos=print):
        self.itemList = itemList
        self.printInfos = printInfos
        self.item = None
        self.player = None

    def start(self):
        self.player = mpv.MPV(log_handler=self.mpv_log, ytdl=True,
                input_default_bindings=True, input_vo_keyboard=True)
        self.player.force_window = True

        @self.player.on_key_press('q')
        def my_q_binding():
            pass

        @self.player.on_key_press('s')
        def my_s_binding():
            self.stop()

        @self.player.property_observer('eof-reached')
        def updatePlayed(_name, value):
            if True == value:
                db = self.itemList.db
                self.item['status'] = 'old'
                db.updateItem(self.item)
                self.itemList.updatesAreas()
                self.item = None
                del db

    def mpv_log(self, loglevel, component, message):
        pass


    def play(self, item, mode='append-play'):
        self.item = item

        self.printInfos('Play '+item['title'])

        needNext = True
        if not self.player:
            needNext = False
            self.start()

        if '' != item['filename']:
            target=item['filename']
        else:
            target=item['link']

        self.player.loadfile(target, 'replace')
        # FIXME append-play does not do play!
        #self.player.play(item['filename'])

    def next(self):
        self.player.playlist_next(mode='force')

    def prev(self):
        self.player.playlist_prev(mode='force')

    def add(self, item):
        if '' != item['filename']:
            target=item['filename']
        else:
            target=item['link']

        self.player.loadfile(target, 'append')

    def stop(self):
        if self.player:
            #self.player.quit_watch_later()
            self.player.write_watch_later_config() # FIXME do not work
            self.player.command('stop')
            del self.player
            self.player = None
