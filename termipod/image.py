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
import sys

try:
    from PIL import Image
    _has_pil = True
except ModuleNotFoundError:
    _has_pil = False


# stdout write inspired from ranger (https://ranger.github.io)
display_protocol = "\033"
close_protocol = "\a"
if "screen" in os.environ['TERM']:
    display_protocol += "Ptmux;\033\033"
    close_protocol += "\033\\"
display_protocol += "]20;"
image_shown = False


def draw(path, screen=None,
         origin=None, coords=None, constraint=None, value=None):
    global image_shown

    if not path:
        return
    if None in (screen, origin, coords, constraint, value):
        py, px, pheight, pwidth = 0, 0, 100, 100
    else:
        sizes = compute_sizes(path, screen, origin, coords, constraint, value)
        if not sizes:
            return None
        py, px, pheight, pwidth = sizes

    sys.stdout.write(
        display_protocol
        + path
        + f';{pwidth}x{pheight}+{px}+{py}:op=keep-aspect'
        + close_protocol
    )
    sys.stdout.flush()
    image_shown = True


def clear(force=False):
    global image_shown
    if not image_shown and not force:
        return

    sys.stdout.write(
        display_protocol
        + ';100x100+1000+1000'
        + close_protocol
    )
    sys.stdout.flush()

    image_shown = False


def compute_sizes(img, screen, origin, coords, constraint, value):
    if origin not in ('upper-right', 'middle', 'middle-right'):
        raise(ValueError(f'Bad origin type {origin}'))
    if constraint not in ('height', 'width'):
        raise(ValueError(f'Bad constraint type {constraint}'))

    font_ratio = 2
    # Screen size
    screen_height, screen_width = screen.getmaxyx()

    img_width, img_height = image_size(img)

    if constraint == 'height':
        height = value
        width = height/img_height*img_width*font_ratio
    else:
        width = value
        height = width/img_width*img_height/font_ratio

    if origin == 'upper-right':
        y_middle = coords[0]+height/2
        x_middle = coords[1]-width/2
    elif origin == 'middle':
        y_middle = coords[0]
        x_middle = coords[1]
    if origin == 'middle-right':
        y_middle = coords[0]
        x_middle = coords[1]-width/2

    # Compute percent height
    pheight = round(height/screen_height*100)

    # Compute percent position
    py = y_middle/screen_height*100
    # Fix 'py' since reference point is top for 0,
    # middle for 50 and bottom for 100
    py = round(50/(50-pheight/2)*py+50*pheight/(pheight-100))

    # X position
    pwidth = round(width/screen_width*100)
    px = x_middle/screen_width*100
    px = round(50/(50-pwidth/2)*px+50*pwidth/(pwidth-100))

    return (py, px, pheight, pwidth)


def image_size(filename):
    if _has_pil:
        try:
            with Image.open(filename) as img:
                return img.size
        except OSError:
            return None
    else:
        return None


def compatible(print_infos):
    if _has_pil:
        return True
    else:
        print_infos('You need to install PIL python package first!', mode='error')
        return False
