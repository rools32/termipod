# -*- coding: utf-8 -*-
#
# termipod
# Copyright (c) 2020 Cyril Bordage
#
# termipod is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# termipod is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
import os
import os.path
import urllib

import termipod.config as Config


def item_get_filename(item, what):
    if 'channel' in item:  # Medium
        h = hash(('medium', what, item['link'], item['cid']))

    else:  # Channel
        h = hash(('channel', what, item['id']))

    ext = os.path.splitext(item[what])[1]

    return f'{Config.thumbnail_path}/{h}{ext}'


def item_get_cache(item, what, print_infos):
    if not item[what]:
        return ''
    filename = item_get_filename(item, what)
    url = item[what]

    if not os.path.isfile(filename):
        try:
            urllib.request.urlretrieve(url, filename)
        except urllib.error.URLError:
            print_infos('Cannot access to %s' % url, mode='error')
            return ''

    return filename
