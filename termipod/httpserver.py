# from twisted.web import server, resource
# from twisted.internet import reactor, endpoints

import tempfile
import multiprocessing
import urllib
import os
import stat
from io import SEEK_CUR
import time
import datetime
import atexit

try:
    import twisted
    from twisted.web.server import Site
    from twisted.web.static import File, DirectoryLister
    from twisted.internet import reactor
    _has_twisted = True
except ModuleNotFoundError:
    _has_twisted = False
    File = object
    DirectoryLister = object

    from urllib.parse import unquote

import termipod.config as Config
from termipod.utils import format_size
from termipod.fuse import mountpoint as fuse_mountpoint


class RemoteFile(File):
    indexNames = []

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
                    line = line.strip()

                    # Directive
                    if not line or line.startswith(b'#'):
                        pass

                    # If local file, we make a URL
                    elif b'://' not in line:
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

    def listNames(self):
        if not self.isdir():
            return []
        directory = reversed(self.listdir())
        return directory

    def directoryListing(self):
        """
        Return a resource that generates an HTML listing of the
        directory this path represents.

        @return: A resource that renders the directory to HTML.
        @rtype: L{DirectoryLister}
        """
        path = self.path
        names = self.listNames()
        return CustomDirectoryLister(path,
                                     names,
                                     self.contentTypes,
                                     self.contentEncodings,
                                     self.defaultType)


class CustomDirectoryLister(DirectoryLister):
    template = """
<html>
<head>
<title>%(header)s</title>
<style>
.even-dir { background-color: #efe0ef }
.even { background-color: #eee }
.odd-dir {background-color: #f0d0ef }
.odd { background-color: #dedede }
.icon { text-align: center }
.listing {
    margin-left: auto;
    margin-right: auto;
    width: 50%%;
    padding: 0.1em;
}
.right {
    text-align: right;
    margin-right: 1em;
}


body { border: 0; padding: 0; margin: 0; background-color: #efefef; }
h1 {padding: 0.1em; background-color: #777; color: white; border-bottom: thin white dashed;}

</style>
</head>

<body>
<h1>%(header)s</h1>

<table>
    <thead>
        <tr>
            <th>Filename</th>
            <th>Length</th>
            <th>Date</th>
        </tr>
    </thead>
    <tbody>
%(tableContent)s
    </tbody>
</table>

</body>
</html>
"""

    linePattern = """
        <tr class="%(class)s">
            <td><a href="%(href)s">%(text)s</a></td>
            <td class=right>%(duration)s</td>
            <td>%(date)s</td>
        </tr>
    """

    def _getFilesAndDirectories(self, directory):
        dirs, files = super()._getFilesAndDirectories(directory)

        for p in dirs+files:
            complete_path = f'{self.path}/{unquote(p["href"])}'
            st = os.lstat(complete_path)

            size = st.st_size
            if complete_path.startswith(fuse_mountpoint):
                if stat.S_ISLNK(st.st_mode):
                    p['duration'] = '%3d:%02d' % (size // 60, size % 60)
                elif stat.S_ISDIR(st.st_mode):
                    p['duration'] = size
                else:
                    p['duration'] = format_size(size)
            else:
                p['duration'] = format_size(size)

            ctime = st.st_ctime
            p['date'] = datetime.datetime.fromtimestamp(
                int(ctime)).strftime('%Y-%m-%d')

        return dirs, files


class HTTPServer():
    def __init__(self, port=None, start=None, print_infos=print):
        if port is None:
            port = Config.get('Global.httpserver_port')
        if start is None:
            start = Config.get('Global.httpserver_start')

        self.port = port
        self.print_infos = print_infos
        self.server_process = None
        if start:
            self.start()
        atexit.register(self.stop)

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
