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

import logging
from functools import wraps
from http.client import NOT_FOUND

import requests
from django.conf import settings
from django.db.models import Q

from ..models import Chassis, Node, NodeGroup, Rack, Room, Row

__all__ = ['sync2db', 'sync2confluent']

logger = logging.getLogger(__name__)


def red_string(string):
    return '\033[31m{}\033[0m'.format(string)


def check_location_u(func):
    @wraps(func)
    def _wrap(configure):
        unique_info = {}
        for chassis in configure.chassis:
            if chassis.location_u_in_rack < 1:
                prompt = 'The location_u_in_rack value in chassis({0}) ' \
                         'has to be greater than 0'.format(chassis.name)
                raise SystemExit(red_string(prompt))
            key = (chassis.rack.name, '', chassis.location_u_in_rack)
            value = unique_info.get(key)
            if value is not None:
                type_name = "{0}: {1}, {2}: {3}".format(
                              value['type'], value['name'],
                              'chassis', chassis.name
                            )
                msg = "(rack: {0}, location_u: {1})".format(key[0], key[2])
                prompt = 'Find two invalid lines in nodes.csv:\n{0}\n' \
                         'contain the same{1}'.format(type_name, msg)
                raise SystemExit(red_string(prompt))
            unique_info[key] = {'type': 'chassis', 'name': chassis.name}
        for node in configure.node:
            if node.location_u < 1:
                prompt = 'The location_u value in node({0}) ' \
                         'has to be greater than 0'.format(node.name)
                raise SystemExit(red_string(prompt))
            key = (node.rack.name, node.chassis.name, node.location_u) \
                if node.chassis else (node.rack.name, '', node.location_u)
            value = unique_info.get(key)
            if value is not None:
                type_name = "{0}: {1}, {2}: {3}".format(
                    value['type'], value['name'],
                    'node', node.name
                )
                if not key[1]:
                    msg = "(rack: {0}, location_u: {1})".format(key[0], key[2])
                else:
                    msg = "(rack: {0}, chassis: {1}, location_u: {2})".format(
                        *key
                    )
                prompt = 'Find two invalid lines in nodes.csv:\n{0}\n' \
                         'contain the same{1}'.format(type_name, msg)
                raise SystemExit(red_string(prompt))
            unique_info[key] = {'type': 'node', 'name': node.name}

        return func(configure)
    return _wrap


@check_location_u
def sync2db(configure):
    _sync_rooms(configure)
    _sync_groups(configure)
    _sync_rows(configure)
    _sync_racks(configure)
    _sync_chassis(configure)
    _sync_nodes(configure)

    _clear_clusterinfo(configure)


def sync2confluent(configure):
    for node in configure.node:
        if fetch_confluent_node(node) is not None:
            modify_confluent_node(node)
        else:
            add_confluent_node(node)


def _sync_rooms(configure):
    for room in configure.room:
        Room.objects.update_or_create(
            name=room.name,
            defaults=dict(
                location=room.location_description
            )
        )


def _sync_groups(configure):
    for group in configure.group:
        NodeGroup.objects.update_or_create(
            name=group.name
        )


def _sync_rows(configure):
    for row in configure.row:
        Row.objects.update_or_create(
            name=row.name,
            defaults=dict(
                index=row.index,
                room=Room.objects.get(
                    name=row.room.name
                )
            )
        )


def _sync_racks(configure):
    for rack in configure.rack:
        Rack.objects.update_or_create(
            name=rack.name,
            defaults=dict(
                col=rack.column,
                row=Row.objects.get(
                    name=rack.row.name
                )
            )
        )


def _sync_chassis(configure):
    for chassis in configure.chassis:
        rack = Rack.objects.get(name=chassis.rack.name)
        Chassis.objects.update_or_create(
            name=chassis.name,
            defaults=dict(
                location_u=chassis.location_u_in_rack,
                rack=rack,
                machine_type=chassis.machine_type,
            )
        )


def _sync_nodes(configure):
    for node in configure.node:
        rack = Rack.objects.get(name=node.rack.name)
        chassis = Chassis.objects.get(name=node.chassis.name) \
            if node.chassis else None

        obj = Node.objects.update_or_create(
            hostname=node.name,
            defaults=dict(
                type=node.nodetype,
                machinetype=node.machine_type,
                mgt_address=node.hostip,
                bmc_address=node.immip,
                location_u=node.location_u,
                rack=rack,
                chassis=chassis,
                manage_method=node.manage_method,
                vendor=node.vendor
            )
        )[0]

        for group in NodeGroup.objects.iterator():
            group.nodes.remove(obj)
        for group in node.group:
            group = NodeGroup.objects.get(name=group.name)
            group.nodes.add(obj)
            group.save()


def _clear_clusterinfo(configure):
    node_names = [node.name for node in configure.node]
    chassis_names = [chassis.name for chassis in configure.chassis]
    rack_names = [rack.name for rack in configure.rack]
    row_names = [row.name for row in configure.row]
    group_names = [group.name for group in configure.group]
    room_names = [room.name for room in configure.room]

    Node.objects.exclude(
        Q(hostname__in=node_names) | Q(on_cloud=True)
    ).delete()
    # delete removed chassis
    Chassis.objects.exclude(Q(name__in=chassis_names)).delete()
    # delete removed racks
    Rack.objects.exclude(
        Q(name__in=rack_names) | Q(on_cloud=True)
    ).delete()
    # delete removed rows
    Row.objects.exclude(
        Q(name__in=row_names) | Q(on_cloud=True)
    ).delete()
    # delete removed groups
    NodeGroup.objects.exclude(
        Q(name__in=group_names) | Q(on_cloud=True)
    ).delete()
    # delete removed rooms
    Room.objects.exclude(
        Q(name__in=room_names) | Q(on_cloud=True)
    ).delete()


def response_from_confluent(url, request_json=None):
    pass


def fetch_confluent_node(node):
    url = 'http://{}:{}/nodes/{}'.format(
        settings.CLUSTER.CONFLUENT.HOST,
        settings.CLUSTER.CONFLUENT.PORT,
        node.name
    )
    response = requests.get(
        url,
        auth=(
            settings.CLUSTER.CONFLUENT.USER,
            settings.CLUSTER.CONFLUENT.PASS
        ),
        headers={"accept": "application/json"},
        timeout=settings.CLUSTER.CONFLUENT.REQUESTS_TIMEOUT
    )

    if response.status_code == NOT_FOUND:
        return None

    response.raise_for_status()

    return response.json()


def add_confluent_node(node):
    url = 'http://{}:{}/nodes'.format(
        settings.CLUSTER.CONFLUENT.HOST,
        settings.CLUSTER.CONFLUENT.PORT
    )

    request_json = {
        'name': node.name,

    }
    if node.immip is not None and len(node.immip) > 0:
        request_json.update({
            'console.method': 'ipmi',
            'hardwaremanagement.manager': node.immip,
            'hardwaremanagement.method': node.manage_method,
        })
        if node.ipmi_user is not None and len(node.ipmi_user) > 0:
            request_json['secret.hardwaremanagementuser'] = node.ipmi_user
        if node.ipmi_pwd is not None and len(node.ipmi_pwd) > 0:
            request_json['secret.hardwaremanagementpassword'] = node.ipmi_pwd

    response = requests.post(
        url,
        auth=(
            settings.CLUSTER.CONFLUENT.USER,
            settings.CLUSTER.CONFLUENT.PASS
        ),
        headers={
            "accept": "application/json"
        },
        json=request_json,
        timeout=settings.CLUSTER.CONFLUENT.REQUESTS_TIMEOUT
    )
    response.raise_for_status()


def modify_confluent_node(node):
    url = 'http://{}:{}/nodes/{}/attributes/current'.format(
        settings.CLUSTER.CONFLUENT.HOST,
        settings.CLUSTER.CONFLUENT.PORT,
        node.name
    )

    if node.immip is not None and len(node.immip) > 0:
        request_json = {
            'console.method': 'ipmi',
            'hardwaremanagement.manager': node.immip,
            'hardwaremanagement.method': node.manage_method,
        }
        if node.ipmi_user is not None and len(node.ipmi_user) > 0:
            request_json['secret.hardwaremanagementuser'] = node.ipmi_user
        if node.ipmi_pwd is not None and len(node.ipmi_pwd) > 0:
            request_json['secret.hardwaremanagementpassword'] = node.ipmi_pwd
    else:
        request_json = {
            'console.method': None,
            'hardwaremanagement.manager': None,
            'secret.hardwaremanagementuser': None,
            'secret.hardwaremanagementpassword': None
        }

    response = requests.put(
        url,
        auth=(
            settings.CLUSTER.CONFLUENT.USER,
            settings.CLUSTER.CONFLUENT.PASS
        ),
        headers={
            "accept": "application/json"
        },
        json=request_json,
        timeout=settings.CLUSTER.CONFLUENT.REQUESTS_TIMEOUT
    )
    response.raise_for_status()
