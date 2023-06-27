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

import json
import logging
from collections import namedtuple
from datetime import datetime

from dateutil.tz import tzutc
from django.conf import settings
from django.db.models import Count
from django.utils.translation import ugettext as _

from .models import Alert, Policy

logger = logging.getLogger(__name__)


def format_nodes_filter_to_db(nodes):
    value_type = nodes['value_type']
    values = nodes['values']
    filter = {
        "value_type": value_type.lower(),
        "values": values
        }
    return '[LICO-FILTER]' + json.dumps(filter)


def parse_nodes_filter_from_db(nodes_text):
    if not nodes_text.startswith('[LICO-FILTER]'):
        nodes = nodes_text.split(';')
        if len(nodes) > 0 and nodes[0].lower() == 'all':
            return {
                'value_type': 'hostname',
                'values': []
                }
        return {
            'value_type': 'hostname',
            'values': nodes
            }
    else:
        return json.loads(nodes_text[13:])


context_tuple = namedtuple(
    "context",
    [
        'data', 'start_time', 'end_time',
        'creator', 'create_time', 'operator'
    ]
)


def _get_datetime(data):
    return datetime.fromtimestamp(
        int(data["start_time"]), tz=tzutc()
    ), datetime.fromtimestamp(
        int(data["end_time"]), tz=tzutc()
    )


def _get_create_info(data):
    return data["creator"], datetime.now(tz=tzutc())


def _query_alarm_info(data):
    alarm_level = {
        '0': None,
        '1': Policy.FATAL,
        '2': Policy.ERROR,
        '3': Policy.WARN,
        '4': Policy.INFO
    }

    start_time, end_time = _get_datetime(data)
    creator, create_time = _get_create_info(data)
    nodes = data.get("node", [])
    level = data.get("event_level", "0")

    query = Alert.objects.filter(
        create_time__gte=start_time,
        create_time__lte=end_time
    )
    if len(nodes) > 0:
        query = query.filter(node__in=[node.strip() for node in nodes])
    # 0: all; 1: fatal; 2:error; 3:warning; 4: info
    if level != "0":
        query = query.filter(policy__level=alarm_level[level])
    objs = query.all().order_by("create_time")
    return objs, start_time, end_time, creator, create_time


def _query_alarm_details(data, fixed_offset):

    objs, start_time, end_time, creator, create_time = _query_alarm_info(data)

    alarm_columns = (
        "create_time", "policy__name", "node",
        "policy__level", "status", "comment"
    )

    # Make level to be consistent with UI
    level_map = {
        Policy.INFO: "Information",
        Policy.WARN: "Warning",
        Policy.ERROR: "Error",
        Policy.FATAL: "Critical"
    }

    status_map = {
        Alert.PRESENT: "Unconfirmed",
        Alert.CONFIRMED: "Confirmed",
        Alert.RESOLVED: "Fixed"
    }
    tmp_values = objs.values_list(*alarm_columns)
    values = []
    for tmp_value in tmp_values:
        value = list(tmp_value)
        value[0] = '{0:%Y-%m-%d %H:%M:%S}'.format(
            value[0].astimezone(fixed_offset)
        )
        value[3] = _(
            level_map[value[3]]
        ) if value[3] in level_map else _(
            Policy.level_value(value[3])
        )
        value[4] = _(
            status_map[value[4]]
        ) if value[4] in status_map else ""

        values.append(value)

    return context_tuple(
        values,
        start_time.astimezone(fixed_offset),
        end_time.astimezone(fixed_offset),
        creator,
        create_time.astimezone(fixed_offset),
        settings.LICO.ARCH
    )._asdict()


def _query_alarm_statistics(data, fixed_offset):
    data["node"], data["event_level"] = [], "0"
    objs, start_time, end_time, creator, create_time = _query_alarm_info(data)

    tmp_values = objs \
        .extra(select={"hour": "alert_alert.create_time"}) \
        .annotate(counts=Count("policy__level")) \
        .values("hour", "policy__level", "counts")

    datas = {}
    init_val = [0, 0, 0, 0, 0]
    level_idx = {
        str(logging.FATAL): 1,
        str(logging.ERROR): 2,
        str(logging.WARN): 3,
        str(logging.INFO): 4
    }

    for tmp_val in tmp_values:
        tmp_val["hour"] = tmp_val["hour"].astimezone(fixed_offset)\
            .strftime("%Y-%m-%d")
        if tmp_val["hour"] not in datas:
            datas[tmp_val["hour"]] = [tmp_val["hour"]] + init_val

        datas[tmp_val["hour"]][
            level_idx[tmp_val["policy__level"]]] += tmp_val["counts"]
        # The last column is total alarm number
        datas[tmp_val["hour"]][-1] += tmp_val["counts"]

    values = datas.values()

    return context_tuple(
        values,
        start_time.astimezone(fixed_offset),
        end_time.astimezone(fixed_offset),
        creator,
        create_time.astimezone(fixed_offset),
        settings.LICO.ARCH
    )._asdict()


def get_hostnames_from_filter(node_filter):
    from lico.core.contrib.client import Client
    client = Client().cluster_client()
    value_type = node_filter['value_type']
    values = node_filter['values']
    hostnames = []
    if values:
        if value_type.lower() == 'hostname':
            hostnames = values
        elif value_type.lower() == 'rack':
            hostnames = get_hostlist_by_rack(
                client, values
            )
        elif value_type.lower() == 'nodegroup':
            hostnames = get_hostlist_by_nodegroup(
                client, values
            )
    return hostnames


def get_hostlist_by_rack(client, values):
    hostnames = []
    racks_nodes = client.get_rack_nodelist()
    for rack_node in racks_nodes:
        if rack_node.name in values:
            hostnames.extend(rack_node.hostlist)
    if len(hostnames) == 0 and len(values) > 0:
        logger.warning("lico not exist hostname")
    return hostnames


def get_hostlist_by_nodegroup(client, values):
    hostnames = []
    groups_nodes = client.get_group_nodelist()
    for group_nodes in groups_nodes:
        if group_nodes.name in values and group_nodes.nodes:
            hostnames.extend(group_nodes.hostlist)
    hostnames = list(set(hostnames))
    if len(hostnames) == 0 and len(values) > 0:
        logger.warning("lico not exist hostname")
    return hostnames
