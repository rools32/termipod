# -*- coding: utf-8 -*-
#
# termipod
# Copyright (c) 2018 Cyril Bordage
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
from datetime import datetime, timedelta
import unicodedata

from termipod.config import log_path


def printable_str(string):
    new_str = ''

    for c in string:
        # For zero-width characters
        if unicodedata.category(c)[0] in ('M', 'C'):
            continue

        w = unicodedata.east_asian_width(c)
        if w in ('N', 'Na', 'H', 'A'):
            new_str += c
        else:
            new_str += '🖥'

    return new_str


def print_log(string):
    if print_log.reset:
        mode = 'w'
        print_log.reset = False
    else:
        mode = 'a'
    filename = log_path
    with open(filename, mode) as myfile:
        myfile.write(str(string)+"\n")
print_log.reset = True


def ts_to_date(ts):
    return datetime.fromtimestamp(int(ts)).strftime('%Y-%m-%d')


def str_to_filename(string):
    return unicodedata.normalize('NFKD', string).encode('ascii', 'ignore')\
            .decode('ascii').replace(' ', '-').replace('/', '-')


def duration_to_str(duration):
    if duration < 0:
        duration = 0
    return str(timedelta(seconds=duration))


def format_string(string, width, truncate=True):
    ''' Truncate the line or add spaces if needed
    When !truncate, list is returned for each line
    '''

    # If line is too long
    if truncate:
        space = width-len(string)
        if 0 > space:
            return string[:space-1]+'…'
        else:
            return string+' '*space

    else:
        strings = []
        string_list = string.split(' ')
        while string_list:
            line = ''
            remain = width
            # We fill in the line
            while string_list and len(string_list[0]) <= remain:
                s = string_list.pop(0)
                line += s+' '
                remain -= len(s)+1

            # Check we got someting to put
            if not line:  # line was too long to be nicely cut
                line = string_list[0][:width]
                string_list[0] = string_list[0][width:]
                strings.append(line)
            else:
                line = line[:-1]  # remove last ' '
                remain += 1
                strings.append(line+' '*remain)

        return strings
