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
from collections import defaultdict

from ..models import Policy
from .datasource import DataSource
from .judge import Judge

logger = logging.getLogger(__name__)

POLICY_MAPPING = {
    "cpu": Policy.CPUSAGE,
    "memory_util": Policy.MEMORY_UTIL,
    "disk": Policy.DISK,
    'node_active': Policy.NODE_ACTIVE,
    "energy": Policy.ELECTRIC,
    "temperature": Policy.TEMP,
    "hardware": Policy.HARDWARE,
    "gpu_util": Policy.GPU_UTIL,
    "gpu_temperature": Policy.GPU_TEMP,
    "gpu_memory": Policy.GPU_MEM,
    "hardware_discovery": Policy.HARDWARE_DISCOVERY,
}


class AlertCheck(object):

    @classmethod
    def _get_policys(cls, metric):
        policy_name = POLICY_MAPPING.get(metric, None)
        policys = []
        if policy_name:
            policys = Policy.objects.filter(
                metric_policy=policy_name,
                status=Policy.ON
            )
        return policys

    @classmethod
    def _alarm(cls, policy):
        targets = DataSource(policy).get_data()
        alarm_list = Judge(targets, policy).compare()
        alarm_data = dict(
            policy_id=policy.id
        )
        policy_name = Policy.objects.get(id=policy.id).metric_policy
        hardware_info = defaultdict(dict)
        # if policy_name == 'HARDWARE_DISCOVERY' and targets:
        import pandas as pd
        if policy_name == 'HARDWARE_DISCOVERY' \
                and isinstance(targets, pd.DataFrame) \
                and targets.empty is False:
            host = targets.to_dict()['node']
            val = targets.to_dict()['val']
            for key, values in host.items():
                hardware_info[values].update(json.loads(val[key]))
        if alarm_list:
            from ..tasks import create_alert
            for alarm in alarm_list:
                alarm_data["node"] = alarm["node"]
                idx = alarm.get("index")
                alarm_data["index"] = idx if idx else None
                alarm_data["comment"] = hardware_info.get(alarm["node"])
                create_alert.delay(alarm_data)
        else:
            logging.info("No alarm object needs to trigger an alarm")

    @classmethod
    def checker(cls, metric):
        policys = cls._get_policys(metric)
        for policy in policys:
            cls._alarm(policy)
