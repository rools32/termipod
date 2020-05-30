# from twisted.web import server, resource
# from twisted.internet import reactor, endpoints

import tempfile
import multiprocessing
import urllib
from io import SEEK_CUR
import time

try:
    import twisted
    from twisted.web.server import Site
    from twisted.web.static import File
    from twisted.internet import reactor
    _has_twisted = True

except ModuleNotFoundError:
    _has_twisted = False


if _has_twisted:
    class RemoteFile(File):
        def render_GET(self, request):
            if self.path.endswith('.m3u'):
                ip = request.host.host
                port = request.host.port
                self.prefix = f'http://{ip}:{port}/'.encode()

            return super().render_GET(request)

        def get_remote_m3u(self):
            try:
                return self.remote_m3u
            except AttributeError:
                file = tempfile.TemporaryFile()
                self.remote_m3u = file
                with self.open() as f:
                    for line in f:
                        line = line[:-1]
                        line = urllib.parse.quote(line).encode()
                        line = self.prefix+line
                        file.write(line+b'\n')
                self.remote_m3u_size = file.seek(0, SEEK_CUR)
                file.seek(0)
                return self.remote_m3u

        def get_remote_m3u_size(self):
            self.get_remote_m3u()
            return self.remote_m3u_size

        def openForReading(self):
            if self.path.endswith('.m3u'):
                return self.get_remote_m3u()

            else:
                return self.open()

        def getFileSize(self):
            if self.path.endswith('.m3u'):
                return self.get_remote_m3u_size()

            else:
                return self.getsize()


class HTTPServer():
    def __init__(self, port, print_infos):
        self.port = port
        self.print_infos = print_infos
        self.server_process = None

    def run(self, port=None):
        if port is None:
            port = self.port
        try:
            file = RemoteFile(".")
            reactor.listenTCP(port, Site(file))
            reactor.run()
        except twisted.internet.error.CannotListenError as e:
            # XXX FIXME problem with print_infos in distributed memory!
            self.print_infos(f'Cannot start server: {e}', mode='error')

    def start(self, port=None):
        # Module twisted is no available
        if not _has_twisted:
            self.print_infos('Cannot start server: "twisted" module is needed',
                             mode='error')
            return

        if self.status(show=False):
            self.print_infos(f'Server already running on port {self.port}',
                             mode='direct')
            return

        if port is None:
            port = self.port
        else:
            self.port = port
        p = multiprocessing.Process(target=self.run, args=(port,))
        p.daemon = True
        self.print_infos(f'Server started on port {port}', mode='direct')
        p.start()

        # NOTE: XXX Hack for non-working print_infos
        time.sleep(.5)
        if not p.is_alive():
            self.print_infos('Cannot start server!', mode='error')
            return

        self.server_process = p

    def status(self, show=True):
        if (self.server_process is not None
                and self.server_process.is_alive()):
            if show:
                self.print_infos(f'Server is running on port {self.port}',
                                 mode='direct')
            return True
        else:
            if show:
                self.print_infos('Server is stopped', mode='direct')
            return False

    def stop(self):
        if (self.server_process is not None
                and self.server_process.is_alive()):
            self.server_process.kill()
            self.print_infos('Server stopped')
            self.server_process = None

        else:
            self.print_infos('Server is not running', mode='error')
