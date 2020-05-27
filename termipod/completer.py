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
import re
import shlex

from termipod.utils import commastr_to_list


class Completer:
    def __init__(self, values):
        self.values = values


class CommaListCompleter(Completer):
    def complete(self, string, selected=''):
        values = commastr_to_list(string, remove_emtpy=False)
        begin = values[:-1]
        lastword = values[-1]
        candidates = [v for v in self.values
                      if v.startswith(lastword) and v not in begin]
        candidates.sort()
        return {'replaced_token': lastword,
                'candidates': candidates,
                'helplines': candidates}


class CommaListSizeCompleter(Completer):
    def complete(self, string, selected=''):
        values = commastr_to_list(string, remove_emtpy=False)
        begin = values[:-1]
        lastword = values[-1]
        candidates = [v for v in self.values
                      if v.startswith(lastword) and v not in begin]
        candidates.sort()
        helps = [f'{c} ({self.values[c]})' for c in candidates]
        return {'replaced_token': lastword,
                'candidates': candidates,
                'helplines': helps}


class CommandCompleter(Completer):
    def __init__(self):
        self.values = []

    def _find_location(self, path, start=None, get_seen_options=False):
        if start is None:
            location = self.values
        else:
            location = start

        # Empty values
        if not location:
            return location

        seen_options = []
        position = 0
        for p in path:
            new_locations = []
            for l in location:
                # If start as option, we avoid it being matched with matchall
                # option
                if l['value'].endswith('=') and p.startswith(l['value']):
                    if re.match('^'+l['regex']+'$', p) is None:
                        return None

                else:
                    if re.match('^'+l['regex']+'$', p) is None:
                        if (l['position'] is not None
                                and l['position'] != position):
                            return None
                        continue
                    else:
                        if (l['position'] is not None
                                and l['position'] != position):
                            continue
                new_locations.append(l)

            if len(new_locations) != 1:
                return None
            new_location = new_locations[0]

            # If it is command (else: it is an option, we ignore it)
            if 'next' in new_location:
                location = new_location['next']
                seen_options = []
                position = 0
            else:
                if not l['repeat']:
                    seen_options.append(new_location['name'])
                position += 1

        if get_seen_options:
            return (location, seen_options, position)
        else:
            return location

    def add_command(self, name, description):
        return self.add_subcommand([], name, description)

    def add_subcommand(self, path, name, description):
        location = self._find_location(path)
        location.append({
            'name': name,
            'value': name,
            'regex': name,
            'position': None,
            'description': description,
            'next': [],
        })

    def add_option(self, path, name, value, regex, description,
                   position=None, repeat=False):
        location = self._find_location(path)
        location.append({
            'name': name,
            'value': value,
            'regex': regex,
            'description': description,
            'position': position,
            'repeat': repeat,
        })

    def complete(self, string, selected=''):
        tokens = shlex.split(string)
        if string and string[-1] == ' ':
            tokens.append('')
        path = tokens[:-1]
        try:
            lastword = tokens[-1]
        except IndexError:
            lastword = ''

        ret = self._find_location(path, get_seen_options=True)
        if ret is not None:
            location, seen_options, position = ret
        else:
            location = None

        # Does not match
        if location is None:
            return {'replaced_token': lastword,
                    'candidates': [],
                    'helplines': ['Syntax error!']}

        # Determine if we have a mandatory parameter at current position
        fixed_position = False
        for l in location:
            if l['position'] == position:
                fixed_position = True
                break

        # Find candidates
        # Remove seen options
        candidates = [
            l for l in location
            if (l['value'].startswith(lastword) or not l['value']
                or (l['value'][-1] == '=' and lastword.startswith(l['value'])))
            and l['name'] not in seen_options
        ]
        candidates.sort(key=lambda c: c['name'])

        # Remove options at other positions
        if fixed_position:
            candidates = [c for c in candidates if c['position'] == position]
        else:
            candidates = [c for c in candidates if c['position'] is None]

        values = [c['value'] for c in candidates]
        descriptions = [
            c['value']+' -  '+c['description'] if c['value']
            else c['description']
            for c in candidates
        ]

        return {'replaced_token': lastword,
                'candidates': values,
                'helplines': descriptions}
