# Copyright 2015-present Lenovo
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import csv
import re
import socket
from itertools import chain, takewhile

__all__ = ['Configure', 'ObjectNotFound']


class ObjectNotFound(Exception):
    pass


def _find(name, iterable):
    for obj in iterable:
        if obj.name == name:
            return obj
    else:
        raise ObjectNotFound(
            "Can't find object {0}".format(name)
        )


def _filter_encrypt(val):
    if val is None or len(val.strip()) == 0 or val.startswith('*'):
        return None
    else:
        return val


class Room:
    def __init__(self, name, location_description):
        self.name = name
        self.location_description = location_description.strip()


class Group:
    def __init__(self, name):
        self.name = name


class Row:
    def __init__(self, name, index, belonging_room):
        self.name = name.strip()
        self.index = int(index.strip())
        self.belonging_room = belonging_room.strip()
        self.configure = None

    @property
    def room(self):
        return _find(
            self.belonging_room,
            self.configure.room
        )


class Rack:
    def __init__(self, name, column, belonging_row):
        self.name = name.strip()
        self.column = int(column.strip())
        self.belonging_row = belonging_row.strip()
        self.configure = None

    @property
    def row(self):
        return _find(
            self.belonging_row,
            self.configure.row
        )


class Chassis(object):
    def __init__(
            self, name, belonging_rack,
            location_u_in_rack, machine_type
    ):
        self.name = name.strip()
        self.belonging_rack = belonging_rack.strip()
        self.location_u_in_rack = int(location_u_in_rack.strip())
        self.machine_type = machine_type.strip()
        self.configure = None

    @property
    def rack(self):
        return _find(
            self.belonging_rack,
            self.configure.rack
        )


class Node:
    def __init__(
            self, name, nodetype,
            immip, hostip, machine_type,
            ipmi_user, ipmi_pwd,
            belonging_rack, belonging_chassis,
            location_u, groups, manage_method=None, vendor=None, *args, **argv
    ):
        self.name = name.strip()
        self.nodetype = nodetype.strip()
        self.immip = immip.strip() if len(immip.strip()) > 0 else None
        self.hostip = hostip.strip() \
            if len(hostip.strip()) > 0 else socket.gethostbyname(self.name)
        self.machine_type = machine_type.strip()
        self.ipmi_user = _filter_encrypt(ipmi_user.strip())
        self.ipmi_pwd = _filter_encrypt(ipmi_pwd.strip())
        self.manage_method = manage_method \
            if manage_method is None else manage_method.strip()
        self.vendor = vendor if vendor is None else vendor.strip()
        self.belonging_rack = belonging_rack.strip() \
            if len(belonging_rack.strip()) > 0 else None
        self.belonging_chassis = belonging_chassis.strip() \
            if len(belonging_chassis.strip()) > 0 else None
        self.location_u = int(location_u.strip())
        self.groups = groups.strip() \
            if len(groups.strip()) > 0 else None
        self.configure = None

    @property
    def rack(self):
        if self.chassis is not None:
            return self.chassis.rack
        else:
            return _find(
                self.belonging_rack,
                self.configure.rack
            ) if self.belonging_rack is not None else None

    @property
    def chassis(self):
        return _find(
            self.belonging_chassis,
            self.configure.chassis
        ) if self.belonging_chassis is not None else None

    @property
    def group(self):
        if self.groups is None:
            return [_find(
                self.nodetype,
                self.configure.group
            )]
        else:
            return [
                _find(group.strip(), self.configure.group)
                for group in self.groups.split(';') + [self.nodetype]
            ]


class Configure(object):
    type_mapping = {
        'room': Room,
        'group': Group,
        'row': Row,
        'rack': Rack,
        'chassis': Chassis,
        'node': Node
    }
    pattern = re.compile(r'^\*?(.*)$')

    def __init__(
            self, room, group, row, rack, chassis, node
    ):
        self.room = room
        self.group = group
        self.row = row
        self.rack = rack
        self.chassis = chassis
        self.node = node

        if not list(filter(lambda group: group.name == 'login', self.group)):
            self.group.append(
                Group(name='login')
            )

        if not list(filter(lambda group: group.name == 'head', self.group)):
            self.group.append(
                Group(name='head')
            )

        if not list(filter(lambda group: group.name == 'compute', self.group)):
            self.group.append(
                Group(name='compute')
            )

        if not list(filter(lambda group: group.name == 'service', self.group)):
            self.group.append(
                Group(name='compute')
            )

        if not list(filter(lambda group: group.name == 'io', self.group)):
            self.group.append(
                Group(name='io')
            )

        for obj in chain(
            self.row, self.rack,
            self.chassis, self.node
        ):
            obj.configure = self

    @classmethod
    def parse(cls, filename):
        with open(filename, "rb") as f:
            import io

            import chardet
            content = f.read()
            encoding = chardet.detect(content)['encoding']
            f = io.StringIO(content.decode(
                encoding if encoding == 'utf-8' else 'gbk'
            ))
            sections = dict(
                cls._split_sect(
                    csv.reader(
                        (
                            line for line in f
                            if not re.match(r'^[\"\']?\s*#', line)
                        )
                    )
                )
            )

        return cls(**sections)

    @classmethod
    def _split_sect(cls, iterable):
        sect = []
        for row in iterable:
            row = [col.strip() for col in row]

            # empty line
            if all((len(col) == 0 for col in row)):
                pass
            # title line
            elif len(row[0]) > 0:
                # extern title line
                if len(sect) > 0:
                    yield cls._parse_sect(sect)
                sect = [row]
            # gernal line
            else:
                # extern title line
                if len(sect) > 0:
                    sect.append(row)

        if len(sect) > 0:
            yield cls._parse_sect(sect)

    @classmethod
    def _parse_sect(cls, sect):
        tip_list = [
            cls.pattern.match(tip.lower()).groups()[0]
            for tip in takewhile(
                lambda col: len(col) > 0, sect[0]
            )
        ]
        typename = tip_list[0]
        field_names = tip_list[1:]
        container = cls.type_mapping[typename]

        return typename, [
            container(**dict(zip(field_names, row[1:])))
            for row in sect[1:]
        ]
