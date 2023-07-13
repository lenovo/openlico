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

from django.db.models import Count, Max, Min
from rest_framework import status
from rest_framework.response import Response

from lico.core.contrib.authentication import (
    JWTInternalAnonymousAuthentication, RemoteJWTWebAuthentication,
)
from lico.core.contrib.permissions import AsUserRole
from lico.core.contrib.schema import json_schema_validate
from lico.core.contrib.views import APIView, DataTableView, InternalAPIView
from lico.core.monitor_host.exceptions import (
    HostNameDoesNotExistException, SSHConnectException,
)
from lico.core.monitor_host.utils import (
    NodeSchedulerProcess, parse_gpu_logical_info,
)
from lico.ssh.ssh_connect import RemoteSSH

from ..models import Gpu, MonitorNode
from ..utils import (
    BUSY_THRESHOLD, IDLE_THRESHOLD, ResourceFactory,
    get_node_status_preference, node_check,
)

logger = logging.getLogger(__name__)


class NodeHardwareView(DataTableView):
    def _trans_result(self, result, request, busy_nodes):
        result_dict = self.trans_result(result)
        result_dict["gpu"] = self.get_gpu_logical_info(result_dict)

        metric_mapping = {
            'power': 'energy',
            'cpu_load': 'load',
            'temperature': 'temperature',
            'node_active': 'power_status'
        }
        for key, value in metric_mapping.items():
            res = result_dict.pop(key)
            result_dict[value] = None if res is None or res < 0 else res

        if not result.node_active:
            result_dict["status"] = "off"
            return result_dict

        preference = get_node_status_preference(request.user)
        if preference == "cpu_util":
            cpu_util = result.cpu_util
            if cpu_util is None:
                cpu_util = -1
            if cpu_util > BUSY_THRESHOLD:
                result_dict["status"] = "busy"
            elif cpu_util < IDLE_THRESHOLD:
                result_dict["status"] = "idle"
            else:
                result_dict["status"] = "used"
        else:
            if result.hostname.lower() in busy_nodes:
                result_dict["status"] = "busy"
            else:
                result_dict["status"] = "idle"

        return result_dict

    def get_gpu_logical_info(self, result_dict):
        gpu_count = len(result_dict["gpu"])
        if gpu_count <= 0:
            return {
                'vendor': [],
                'product': [],
                'used': [],
                'logical_dev_info': []
            }

        gpu_dev_dict = dict()
        gpu_dev_metric = ['vendor', 'used', 'product']
        gpu_logical_metric = 'logical_dev_info'

        for dev_metric in gpu_dev_metric:
            gpu_dev_dict[dev_metric] = [None] * gpu_count
        gpu_dev_dict[gpu_logical_metric] = [list() for i in range(gpu_count)]

        parse_gpu_logical_info(result_dict, gpu_dev_dict)
        return gpu_dev_dict

    def trans_result(self, result):
        result_dict = result.as_dict(
            inspect_related=True,
            related_field_options=dict(
                gpu=dict(
                    inspect_related=True,
                    related_field_options=dict(
                        logical_dev=dict(
                            include=['dev_id', 'metric', 'value'],
                            inspect_related=False
                        )
                    )
                )
            )
        )
        return result_dict

    def get_query(self, request, *args, **kwargs):
        return MonitorNode.objects

    def get(self, request, *args, **kwargs):
        param_args = json.loads(
            request.query_params["args"]
        )
        self.check_param(param_args)
        param_args = self.params(request, param_args)
        query = self.get_query(request, *args, **kwargs)
        query = self.filters(query, param_args.get('filters', []))  # filter
        query = self.global_search(query, param_args)
        query = self.global_sort(query, param_args)

        filtered_total = 0 if query is None else query.count()
        offset = param_args['offset'] \
            if param_args['offset'] < filtered_total else 0
        results = [] if query is None else \
            query[offset:offset + param_args['length']]
        offset = offset + len(results)

        busy_nodes = node_check(to_lowercase=True)

        return Response(
            {
                'offset': offset,
                'total': filtered_total,
                'data': [
                    self._trans_result(
                        result,
                        request,
                        busy_nodes
                    ) for result in results
                ],
            }
        )


class NodeHealthView(APIView):
    def get(self, request):
        args = request.query_params.get('args', '{}')
        try:
            nodes = json.loads(args)["nodes"]
        except Exception:
            node_info = MonitorNode.objects.all()
        else:
            node_info = MonitorNode.objects.filter(hostname__in=nodes)

        return Response({
            "data": [
                node.as_dict(include=['hostname', 'hardware_health'])
                for node in node_info
            ]
        })


class InternalMonitorResourceView(InternalAPIView):
    def get(self, request, resource_type):
        return Response(ResourceFactory().get_res(resource_type))


class NodeProcessView(InternalAPIView, APIView):
    authentication_classes = (
        RemoteJWTWebAuthentication,
        JWTInternalAnonymousAuthentication
    )

    def get(self, request, hostname):
        scheduler_id = request.query_params.get("scheduler_id", None)
        pids = json.loads(request.query_params.get("pids", "[]"))

        conn = RemoteSSH(hostname)
        node_scheduler_process = NodeSchedulerProcess()
        try:
            conn.connection.open()
        except Exception as e:
            raise SSHConnectException from e
        else:
            gpu_process_info = {}
            try:
                node = MonitorNode.objects.filter(hostname=hostname)[0]
                gpu = node.gpu.all()[0]
                if gpu.vendor == Gpu.NVIDIA:
                    gpu_process_info = node_scheduler_process.\
                        get_nvidia_gpu_process_info(hostname, conn)
                elif gpu.vendor == Gpu.INTEL:
                    gpu_process_info = node_scheduler_process.\
                        get_intel_xpu_process_info(hostname, conn)
            except Exception as e:
                logger.warning(e)
            try:
                pid_job_info = node_scheduler_process.get_process_job_info(
                    hostname, conn, scheduler_id)
            except Exception as e:
                logger.warning(e)
                pid_job_info = {}
            pids = node_scheduler_process.get_process_info(
                conn, pid_job_info, gpu_process_info, scheduler_id, pids)
        finally:
            conn.close()
        return Response({
            "data": list(pids.values())
        })

    @staticmethod
    def convert_job_info(job_info):
        """
        :param job_info: {'904': ['2583285', '2583292']}
        :return: {'2583285': '904', '2583292': '904'}
        """
        new_info = {}
        for key, value in job_info.items():
            new_info.update(dict.fromkeys(value, key))
        return new_info


class JobRunningNodeResourceHeatView(APIView):
    permission_classes = (AsUserRole,)
    category_mapping = {
        'cpu': 'cpu_util',
        'memory': 'memory_util',
    }

    @json_schema_validate({
        'type': 'object',
        'properties': {
            'offset': {
                'type': 'integer'
            },
            'currentPage ': {
                'type': 'integer'
            },
            'hostnames ': {
                'type': 'array',
                'items': {
                    'type': 'string'
                }
            },
        },
        'required': [
            'offset', 'currentPage', 'hostnames'
        ]
    })
    def post(self, request, category):
        format_data = {"currentPage": 0, "offset": 0, "total": 0, "nodes": []}
        currentPage = int(request.data["currentPage"])
        offset = int(request.data["offset"])
        nodelist = request.data["hostnames"]
        ncnts = len(nodelist)
        res_type = self.category_mapping[category]
        format_data["total"] = ncnts
        page_up_sum = offset * (currentPage - 1)
        start_idx = 0 if page_up_sum > ncnts else page_up_sum
        results = nodelist[start_idx:start_idx + offset]
        format_data["offset"] = offset
        format_data["currentPage"] = currentPage
        monitor_data = MonitorNode.objects.filter(
            hostname__in=results
        ).as_dict(include=[res_type, 'hostname'])

        for data_dict in monitor_data:
            data_dict['value'] = data_dict.pop(res_type)
        format_data["nodes"].extend(monitor_data)
        return Response(format_data)


class HostNameAPIView(APIView):
    def get(self, request):
        hostname = request.query_params.get('hostname', None)

        if hostname:
            try:
                host_obj = MonitorNode.objects.get(hostname=hostname)
            except Exception as e:
                msg = f"Hostname: {hostname} error!\n {str(e)}"
                logger.exception(msg)
                raise HostNameDoesNotExistException

            return Response({
                "data": {
                    "cpu_socket_num": host_obj.cpu_socket_num,
                    "cpu_thread_per_core": host_obj.cpu_thread_per_core,
                    "cpu_core_per_socket": host_obj.cpu_core_per_socket,
                }
            })


class NodeEditorFixturesView(APIView):
    def get(self, request):
        data = {
            "hardware": self.get_hardware_fixtures()
        }
        return Response(data)

    def get_hardware_fixtures(self):
        attrs_map = {
            "memory_total": "mem",
            "disk_total": "disk",
        }

        data = {}

        for attr, data_key in attrs_map.items():
            min_value = MonitorNode.objects.values(attr).aggregate(Min(attr))
            max_value = MonitorNode.objects.values(attr).aggregate(Max(attr))

            data.update({
                data_key: {
                    "min": min_value[f"{attr}__min"],
                    "max": max_value[f"{attr}__max"],
                },
            })

        # get cpu data - cpu_total is a property so we compute the data in py
        cpus = [m.cpu_total for m in MonitorNode.objects.all()]

        data.update({
            "cpu": {
                "min": min(cpus),
                "max": max(cpus),
            },
        })

        # get gpu data
        min_value = MonitorNode.objects.annotate(
            gpu_count=Count('gpu')
        ).values('gpu_count').aggregate(Min('gpu_count'))

        max_value = MonitorNode.objects.annotate(
            gpu_count=Count('gpu')
        ).values('gpu_count').aggregate(Max('gpu_count'))

        data.update({
            "gpu": {
                "min": min_value["gpu_count__min"],
                "max": max_value["gpu_count__max"],
            }
        })

        return data


class NodesByHardwareView(APIView):
    def get(self, request):
        try:
            cpu_min = float(self.request.GET.get('cpu_min'))
            cpu_max = float(self.request.GET.get('cpu_max'))

            disk_min = float(self.request.GET.get('disk_min'))
            disk_max = float(self.request.GET.get('disk_max'))

            gpu_min = float(self.request.GET.get('gpu_min'))
            gpu_max = float(self.request.GET.get('gpu_max'))

            mem_min = float(self.request.GET.get('mem_min'))
            mem_max = float(self.request.GET.get('mem_max'))
        except (ValueError, TypeError):
            return Response(status=status.HTTP_400_BAD_REQUEST)

        nodes = []

        qs = MonitorNode.objects.annotate(Count('gpu'))
        for item in qs:
            should_append = (
                (item.cpu_total >= cpu_min and
                    item.cpu_total <= cpu_max) and
                (item.disk_total >= disk_min and
                    item.disk_total <= disk_max) and
                (item.gpu__count >= gpu_min and
                    item.gpu__count <= gpu_max) and
                (item.memory_total >= mem_min and
                    item.memory_total <= mem_max)
            )
            if should_append:
                nodes.append({"hostname": item.hostname})

        return Response(nodes)
