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

import json
import logging

from lico.core.monitor_host.models import HardwareHealth, MonitorNode
from lico.core.monitor_host.utils import ClusterClient, InfluxClient

logger = logging.getLogger(__name__)

_HEALTH_SQL = """\
select host, LAST(value) as value from node_metric
WHERE metric='node_health' and time > now() - 1m GROUP BY host;
"""


def _get_healths():
    return list(InfluxClient().get(_HEALTH_SQL).get_points())


def insert_data_to_hardwarehealth():
    hostlist = ClusterClient().get_hostlist()
    data = _get_healths()
    for healths in data:
        hostname = healths['host']
        if hostname not in hostlist:
            continue
        health_info = json.loads(healths['value'])
        health = health_info['health']
        if health == 'Exception':
            continue
        node, _ = MonitorNode.objects.update_or_create(
            hostname=hostname,
            # Health information cannot display
            # when state field length more than 100 characters
            defaults={'health': health[:100]}
        )
        sensor_names = []
        for sensor in health_info['badreadings']:
            name = sensor.get('name', '')
            sensor_names.append(name)
            HardwareHealth.objects.update_or_create(
                monitor_node=node,
                name=name,
                defaults={
                    # Health information cannot display
                    # when state field length more than 100 characters
                    'health': sensor.get('health', '')[:100],
                    'states': sensor.get('states', ''),
                    'units': sensor.get('units', ''),
                    'value': sensor.get('value', ''),
                    'type': sensor.get('type', '')
                }
            )
        HardwareHealth.objects.filter(
            monitor_node=node
        ).exclude(name__in=sensor_names).delete()
