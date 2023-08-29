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

from lico.core.monitor_host.models import Cluster

logger = logging.getLogger(__name__)


class DataSource:
    def get_cluster_data(self):
        metric_mapping = {
            "cpu_count": int,
            "gpu_allocable_total": int,
            "gpu_allocable_used": int,
            "disk_total": float,
            "disk_used": float,
            "memory_total": float,
            "memory_used": float,
            "eth_out": float,
            "eth_in": float,
            "ib_out": float,
            "ib_in": float,
        }
        cluster_data = Cluster.objects.filter(
            metric__in=list(metric_mapping.keys())
        ).as_dict(include=['metric', 'value'])
        datasource = dict(
            map(
                lambda x: (
                    x['metric'], metric_mapping[x['metric']](x['value'])
                ),
                cluster_data)
        )
        if datasource.get('gpu_allocable_total') == 0:
            datasource.pop('gpu_allocable_total')
            datasource.pop('gpu_allocable_used')
        return datasource
