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

import logging

from django.conf import settings

from lico.core.contrib.client import Client

from ..models import Policy
from .base import Base

logger = logging.getLogger(__name__)

METHOD_MAPPING = {
    Policy.CPUSAGE: "_get_cpu",
    Policy.MEMORY_UTIL: "_get_memory_util",
    Policy.DISK: "_get_disk",
    Policy.NODE_ACTIVE: "_get_node_active",
    Policy.ELECTRIC: "_get_energy",
    Policy.TEMP: "_get_temp",
    Policy.HARDWARE: "_get_hardware_health",
    Policy.GPU_UTIL: "_get_gpu_util",
    Policy.GPU_TEMP: "_get_gpu_temp",
    Policy.GPU_MEM: "_get_gpu_mem",
    Policy.HARDWARE_DISCOVERY: "_get_hardware_dis"
}


class DataSource(Base):
    def __init__(self, policy):
        super().__init__(policy)
        self._caller = getattr(self, METHOD_MAPPING[policy.metric_policy])

    def _get_common_data(self, sql):
        client = Client().influxdb_client()
        from pandas import DataFrame as df
        result = client.query(sql).get_points()
        df_result = df.from_records(result)
        if self._nodes and 'node' in df_result.columns:
            df_result = df_result[df_result['node'].isin(self._nodes)]
        return df_result

    def _get_cpu(self):  # nosec B608
        sql = f"select host as node, value as val " \
              f"from node_metric " \
              f"where metric='cpu_util' and " \
              f"time > now() - {self._duration}s " \
              f"group by host"

        return self._get_common_data(sql)

    def _get_memory_util(self):  # nosec B608
        sql = f"select host as node, value as val " \
              f"from node_metric " \
              f"where metric='memory_util' and " \
              f"time > now() - {self._duration}s " \
              f"group by host"

        return self._get_common_data(sql)

    def _get_disk(self):  # nosec B608
        sql = f"select host as node, value as val " \
              f"from node_metric " \
              f"where metric='disk_util' and " \
              f"time > now() - {self._duration}s " \
              f"group by host"
        return self._get_common_data(sql)

    def _get_energy(self):  # nosec B608
        sql = f"select host as node, value as val " \
              f"from node_metric " \
              f"where metric='node_power' and " \
              f"time > now() - {self._duration}s " \
              f"group by host"
        return self._get_common_data(sql)

    def _get_temp(self):  # nosec B608
        sql = f"select host as node, value as val " \
              f"from node_metric " \
              f"where metric='node_temp' and " \
              f"time > now() - {self._duration}s " \
              f"group by host"
        return self._get_common_data(sql)

    def _get_gpu_util(self):  # nosec B608
        sql = f"select host as node, value as val, index " \
              f"from gpu_metric " \
              f"where metric='gpu_util' and " \
              f"time > now() - {self._duration}s " \
              f"group by host"
        data = self._get_common_data(sql)
        return self._exclude_mig_device(data)

    def _get_gpu_temp(self):  # nosec B608
        sql = f"select host as node, value as val, index " \
              f"from gpu_metric " \
              f"where metric='gpu_temp' and " \
              f"time > now() - {self._duration}s " \
              f"group by host"
        return self._get_common_data(sql)

    def _get_gpu_mem(self):  # nosec B608
        sql = f"select host as node, value as val, index " \
              f"from gpu_metric " \
              f"where metric='gpu_mem_usage' and " \
              f"time > now() - {self._duration}s " \
              f"group by host"
        data = self._get_common_data(sql)
        return self._exclude_mig_device(data)

    def _get_hardware_health(self):  # nosec B608
        sql = f"select host as node, value as val " \
              f"from node_metric " \
              f"where metric='node_health' and " \
              f"time > now() - {self._duration}s " \
              f"group by host"
        return self._get_common_data(sql)

    def _get_node_active(self):  # nosec B608
        sql = f"select host as node, value as val " \
              f"from node_metric " \
              f"where metric='node_active' and " \
              f"time > now() - {self._duration}s " \
              f"group by host"
        return self._get_common_data(sql)

    def _get_hardware_dis(self):  # nosec B608
        sql = f"select host as node, LAST(value) as val " \
              f"from node_metric " \
              f"where metric='hardware_discovery' and " \
              f"time > now() - {self._duration}s " \
              f"group by host"
        return self._get_common_data(sql)

    def _exclude_mig_device(self, data):
        monitor_client = Client().monitor_client()
        node_info = monitor_client.get_cluster_resource()
        node_set = set(data['node'])
        for info in node_info:
            if info.hostname not in node_set:
                continue
            node_required = data['node'].map(lambda x: x == info.hostname)
            for gpu_info in info.data.get(
                    f'{settings.ALERT.Gpu}_mig_mode', []):
                if gpu_info.usage:
                    logger.warning(
                        f"Skip the GPU {gpu_info.index}"
                        f" with MIG enabled on node {info.hostname}."
                    )
                    gpu_index_required = data[
                        'index'].map(lambda x: x == str(gpu_info.index))
                    data.drop(
                        index=data[node_required & gpu_index_required].index,
                        inplace=True
                        )
        return data

    def get_data(self):
        return self._caller()
