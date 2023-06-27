# Copyright 2015-2023 Lenovo
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

from django.core.validators import validate_ipv46_address
from django.db.models import (
    PROTECT, BooleanField, CharField, DateTimeField, ForeignKey, IntegerField,
    ManyToManyField, TextField,
)

from lico.core.contrib.models import Model


class Node(Model):
    hostname = CharField(null=False, unique=True, max_length=255)
    type = TextField(null=False,)
    machinetype = TextField(null=False)
    mgt_address = TextField(null=False, validators=[validate_ipv46_address])
    bmc_address = TextField(null=True, validators=[validate_ipv46_address])
    location_u = IntegerField(null=False, default=1)
    on_cloud = BooleanField(default=False)
    rack = ForeignKey(
        'Rack', null=False, on_delete=PROTECT, related_name='nodes'
    )
    chassis = ForeignKey('Chassis', null=True, on_delete=PROTECT)

    @property
    def location(self):
        return {
            'rack_id': self.rack.pk,
            'u': str(self.location_u),
            'chassis_id': 'null' if self.chassis is None else self.chassis.pk
        }

    def as_dict_on_finished(
        self, result, is_exlucded, **kwargs
    ):
        if not is_exlucded('location'):
            result['location'] = self.location

        return result


class NodeGroup(Model):
    name = CharField(null=False, unique=True, max_length=255)
    on_cloud = BooleanField(default=False)
    nodes = ManyToManyField(Node, related_name='groups')


class Rack(Model):
    name = CharField(null=False, unique=True, max_length=255)
    col = IntegerField(null=False)
    row = ForeignKey('Row', null=True, on_delete=PROTECT, related_name='racks')
    on_cloud = BooleanField(default=False)

    @property
    def location(self):
        return {
            'row_index': 'null' if self.row is None else self.row.index,
            'col_index': self.col
        }

    @property
    def node_num(self):
        return self.nodes.count()

    def as_dict_on_finished(
        self, result, is_exlucded, **kwargs
    ):
        if not is_exlucded('location'):
            result['location'] = self.location
        if not is_exlucded('node_num'):
            result['node_num'] = self.node_num
        return result


class Chassis(Model):
    name = CharField(null=False, unique=True, max_length=255)
    location_u = IntegerField(default=1)
    rack = ForeignKey(
        'Rack', null=True, on_delete=PROTECT, related_name='chassis'
    )
    machine_type = TextField(null=False)

    @property
    def location(self):
        return {
            'rack_id': self.rack.pk,
            'u': str(self.location_u)
        }


class Row(Model):
    name = CharField(null=False, unique=True, max_length=255)
    index = IntegerField(null=False)
    room = ForeignKey(
        'Room', null=True, on_delete=PROTECT, related_name='rows'
    )
    on_cloud = BooleanField(default=False)


class Room(Model):
    name = CharField(null=False, unique=True, max_length=255)
    location = TextField(null=False)
    on_cloud = BooleanField(default=False)


class Asyncid(Model):
    asyncid = CharField(null=False, max_length=32)
    sessionid = CharField(null=False, max_length=32)
    ipaddr = CharField(null=False, max_length=32)
    session = CharField(null=True, max_length=32)
    create_time = DateTimeField(auto_now_add=True)
