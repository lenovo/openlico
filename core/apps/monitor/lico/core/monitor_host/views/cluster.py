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

from django.conf import settings
from rest_framework.response import Response

from lico.core.contrib.permissions import AsUserRole, IsAnonymousUser
from lico.core.contrib.views import APIView
from lico.core.monitor_host.models import Gpu, MonitorNode, NodeSchedulableRes
from lico.core.monitor_host.utils import (
    ClusterClient, get_node_statics, get_node_status_preference,
)

from ..datasource import DataSource

logger = logging.getLogger(__name__)


class ClusterOverview(APIView):
    permission_classes = (AsUserRole,)

    def get(self, request):
        from lico.core.contrib.client import Client
        job_client = Client().job_client()
        running_job_resource = job_client.get_running_job_resource()
        cluster_ds = DataSource().get_cluster_data()
        preference = get_node_status_preference(request.user)
        nodelist = ClusterClient().get_nodelist()

        if ['scheduler'] == settings.MONITOR.TARGETS:
            cpu_total = 0
            mem_total = 0
            mem_used = None
            cluster_gpu_total = 0
            cluster_gpu_used = running_job_resource.gpu_total_num

            gpu_code = settings.MONITOR.CLUSTER_GRES.Gpu
            for item in NodeSchedulableRes.objects.iterator():
                cpu_total += item.cpu_total or 0
                mem_total += item.mem_total or 0

                gres = json.loads(item.gres)
                gpu_data = gres.get(gpu_code, {})
                gpu_total = gpu_data.get('total', 0)
                cluster_gpu_total += int(gpu_total)

            if cluster_gpu_total == 0:
                logger.warning(
                    "Cluster does not set GPU. "
                    "gpu_total={}, gpu_used={}.".format(
                        cluster_gpu_total,
                        cluster_gpu_used
                    )
                )
                cluster_gpu_total = None
                cluster_gpu_used = None

            return Response(
                data={
                    'name': settings.LICO.DOMAIN,
                    'processors': {
                        'total': cpu_total,
                        'used': running_job_resource.core_total_num
                    },
                    'memory': {
                        'total': mem_total or None,
                        'used': mem_used
                    },
                    'gpu': {
                        'total': cluster_gpu_total,
                        'used': cluster_gpu_used
                    },
                    'diskspace': {
                        'total': cluster_ds.get('disk_total', None),
                        'used': cluster_ds.get('disk_used', None),
                    },
                }
            )

        return Response(
            data={
                'name': settings.LICO.DOMAIN,
                'nodes': get_node_statics(preference, nodelist),
                'processors': {
                    'total': cluster_ds.get('cpu_count', None),
                    'used': running_job_resource.core_total_num
                },
                'gpu': {
                    'total': cluster_ds.get('gpu_allocable_total', None),
                    'used': running_job_resource.gpu_total_num
                },
                'memory': {
                    'total': cluster_ds.get('memory_total', None),
                    'used': cluster_ds.get('memory_used', None),
                },
                'diskspace': {
                    'total': cluster_ds.get('disk_total', None),
                    'used': cluster_ds.get('disk_used', None),
                },
                'throughput': {
                    'in': cluster_ds.get('eth_in', None),
                    'out': cluster_ds.get('eth_out', None),
                },
                'ib': {
                    'in': cluster_ds.get('ib_in', None),
                    'out': cluster_ds.get('ib_out', None),
                },
            }
        )


class ClusterResourceView(APIView):
    permission_classes = (AsUserRole | IsAnonymousUser,)

    def get(self, request):
        data = defaultdict(lambda: {"idle": 0, "off": 0, "used": 0})
        if not settings.MONITOR.CLUSTER_RESOURCE.display:
            return Response(dict(data))

        # get resource for running jobs
        from lico.core.contrib.client import Client
        job_client = Client().job_client()
        """
        job_detail for example:
        {
            'c1':{'runningjob_num':1, 'core_total_num':10, 'gpu_total_num':0},
            'c2':{'runningjob_num':2, 'core_total_num':10, 'gpu_total_num':0},
            ..
        }
        """
        job_detail = job_client.get_host_resource_used()

        # Statistics cluster resources
        for node in MonitorNode.objects.iterator():
            gpu_total = 0
            for g_info in node.gpu.iterator():
                dev_id_set = set(
                    g_info.gpu_logical_device.values_list('dev_id', flat=True)
                )
                dev_count = len(dev_id_set)
                if g_info.mig_mode and g_info.vendor == Gpu.NVIDIA \
                        or g_info.vendor == Gpu.INTEL:
                    gpu_total += dev_count
                else:
                    gpu_total += 1
            if not node.node_active:
                data['node']['off'] += 1
                data['cpu']['off'] += node.cpu_total
                if gpu_total:
                    data['gpu']['off'] += gpu_total
                continue
            node_job_detail = job_detail.get(node.hostname)
            if node_job_detail:
                data['node']['used'] += 1
                cpu_used = node_job_detail.get("core_total_num", 0)
                data['cpu']['used'] += cpu_used
                data['cpu']['idle'] += node.cpu_total - cpu_used
                if gpu_total:
                    gpu_used = node_job_detail.get("gpu_total_num", 0)
                    data['gpu']['used'] += gpu_used
                    data['gpu']['idle'] += gpu_total - gpu_used
                continue
            data['node']['idle'] += 1
            data['cpu']['idle'] += node.cpu_total
            if gpu_total:
                data['gpu']['idle'] += gpu_total

        """
        data for example:
            {
                "node": {
                    "idle":50,
                    "off": 50,
                    "used": 20
                },
                "cpu": {
                    "idle": 0,
                    "off": 100,
                    "used": 100,
                }
                "gpu": {
                    "idle": 5,
                    "off": 12,
                    "used": 12
                }
            }
        """
        return Response(dict(data))
