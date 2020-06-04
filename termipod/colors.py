import curses


colors = {
    'item': {
        'normal': (-1, -1, False),
        'blackbg': (None, curses.COLOR_BLACK, False),
        'bold': (curses.COLOR_GREEN, None, None),
        'greyedout': (8, None, None),
        'selected': (None, None, True),
        'highlighted': (curses.COLOR_RED, None, None),
    },
    'status': {
        'normal': (-1, -1, True),
    },
    'popup': {
        'normal': (-1, -1, False),
    },
    'title': {
        'normal': (-1, -1, True),
    },
}
color_codes = {}


def init():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_GREEN, -1)
    curses.init_pair(2, -1, -1)
    curses.init_pair(3, curses.COLOR_RED, -1)
    try:
        curses.init_pair(4, 8, -1)  # Grey
    except curses.error:
        curses.init_pair(4, -1, -1)

    for colorpair in range(1, 5):
        fg, bg = curses.pair_content(colorpair)
        colorpair = 20-colorpair
        if fg != -1 or bg != -1:
            if fg == -1:
                inverse_fg = -1
            else:
                inverse_fg = get_inverse_color_num(fg)

            if bg == -1:
                inverse_bg = -1
            else:
                inverse_bg = get_inverse_color_num(bg)

            curses.init_pair(colorpair, inverse_fg, inverse_bg)
        else:
            curses.init_pair(colorpair, fg, bg)


def color_distance(color1, color2):
    dl = [(color1[i]-color2[i])**2 for i in range(3)]
    delta = 2*dl[0]+4*dl[1]+3*dl[2]
    return delta


def get_closest_color(color):
    min_value = 9*1000**2
    idx = -1
    for c in range(curses.COLORS):
        color_to_test = curses.color_content(c)
        value = color_distance(color, color_to_test)
        if value < min_value:
            idx = c
    return idx


def get_inverse_color_num(color_num):
    rgb = curses.color_content(color_num)
    inverse_rgb = tuple(1000-c for c in rgb)
    return get_closest_color(inverse_rgb)


def add_color(style):
    fg, bg, inverse = style
    pair_index = len(color_codes)+1
    curses.init_pair(pair_index, fg, bg)
    inverse = curses.A_REVERSE if inverse else 0
    return curses.color_pair(pair_index) | inverse


def add_style(style, where, new_style_str):
    if new_style_str is None:
        return style

    fg, bg, invert = colors[where][new_style_str]

    if fg is not None:
        style[0] = fg
    if bg is not None:
        style[1] = bg
    if invert is not None:
        style[2] = invert

    return style


def get_style(where, style):
    return list(colors[where][style])


def get_color_from_style(style):
    if None in style:
        raise ValueError('Bad styles')

    style = tuple(style)
    if style not in color_codes:
        color_codes[style] = add_color(style)

    return color_codes[style]


def get_color(where, style):
    return get_color_from_style(colors[where][style])
