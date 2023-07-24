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
from collections import defaultdict

from django.db.models import Count, F
from influxdb.exceptions import InfluxDBClientError, InfluxDBServerError
from rest_framework.response import Response

from lico.core.contrib.permissions import AsOperatorRole, AsUserRole
from lico.core.contrib.schema import json_schema_validate
from lico.core.contrib.views import APIView
from lico.core.monitor_host.exceptions import (
    InfluxDBException, InvalidDeviceIdException,
)
from lico.core.monitor_host.models import Gpu, MonitorNode
from lico.core.monitor_host.utils import (
    ClusterClient, InfluxClient, convert_value, cut_list, get_new_time_rule,
    parse_gpu_logical_info,
)

from .baseview import CATEGORY_MAPPING, ClusterTendencyBaseView

logger = logging.getLogger(__name__)

LAST_VALUE_PERIOD = '30s'


class NodeHistoryGpuView(APIView):
    permission_classes = (AsUserRole,)

    TENDENCY_INTERVAL_TIME = {
        'hour': '30s',
        'day': '12m',
        'week': '1h24m',
        'month': '6h12m'
    }

    def get(self, request, hostname, index, time_unit, category):
        node_obj = MonitorNode.objects.filter(hostname=hostname)
        if not node_obj.exists():
            return Response({})
        dev_id = request.query_params.get('dev_id', None)
        limit_time, span = get_new_time_rule(
            self.TENDENCY_INTERVAL_TIME[time_unit],
            CATEGORY_MAPPING[time_unit]
        )
        if not dev_id:  # gpu
            metric_mapping = {
                "util": "gpu_util",
                "memory": "gpu_mem_usage",
                "temperature": "gpu_temp"
            }
            sql = self.get_sql().format(
                categ=time_unit,
                categ_m=limit_time,
                time=self.TENDENCY_INTERVAL_TIME[time_unit]
            )
            bind_params = {
                "host": hostname,
                "index": index,
                "metric": metric_mapping.get(category)
            }
            logger.info("gpu history sql: %s", sql)
        else:  # logical dev
            # Get device id detail for gpu or xpu
            dev_unique_id_dict = \
                self.get_dev_unique_id(node_obj.first(), index)
            dev_unique_id = dev_unique_id_dict.get(dev_id, None)
            if dev_unique_id is None:
                raise InvalidDeviceIdException

            metric_mapping = {
                "util": "gpu_dev_util",
                "memory": "gpu_dev_mem_usage",
                "temperature": "gpu_dev_temp"
            }
            sql = self.get_logical_dev_sql().format(
                categ=time_unit,
                categ_m=limit_time,
                time=self.TENDENCY_INTERVAL_TIME[time_unit]
            )
            bind_params = {
                "host": hostname,
                "gpu_id": index,
                "dev_id": dev_unique_id,
                "metric": metric_mapping.get(category)
            }
            logger.info("logical device history sql: %s", sql)
        try:
            data = InfluxClient().get(
                sql,
                epoch='s',
                bind_params=bind_params
            )
        except InfluxDBServerError or InfluxDBClientError as e:
            raise InfluxDBException from e
        data = self.handle_query_data(data)
        if data and data[-1].get("value") is None:
            data = cut_list(data, end=len(data) - 1, max_len=span,
                            cut_from_start=False)
        return self.return_success(data)

    def get_dev_unique_id(self, node_obj, index):
        dev_unique_id_dict = dict()
        gpu_obj = node_obj.gpu.filter(index=int(index))
        if not gpu_obj.exists():
            return dev_unique_id_dict
        dev_ids = gpu_obj.first().gpu_logical_device.values_list(
            'dev_id', flat=True
        )
        for dev_gi_ci in set(dev_ids):
            dev_unique_id_dict[dev_gi_ci.split('.')[0]] = dev_gi_ci
        """
        Format for dev_unique_id_dict:
            {
                "device_id": "dev_unique_id",
                ...
            }

        Format for dev_unique_id:
            For nvidia GPU: <device_id.gi_id.ci_id>
            For intel XPU: <title_id>
        """
        return dev_unique_id_dict

    def get_sql(self):
        sql = "select last(value) as value from \"{categ}\".gpu_metric \
        where host=$host and index=$index and metric=$metric \
        and time > now() - {categ_m} group by time({time})"
        return sql

    def get_logical_dev_sql(self):
        sql = "select last(value) as value " \
              "from \"{categ}\".gpu_logical_dev_metric " \
              "where host=$host and gpu_id=$gpu_id and " \
              "dev_id=$dev_id and metric=$metric " \
              "and time > now() - {categ_m} group by time({time})"
        return sql

    def handle_query_data(self, data):
        data = map(convert_value, data.get_points())
        return list(data)

    def return_success(self, data, *args, **kwargs):
        return_data = {
            "msg": "",
            "history": data if data else [],
            'current': data[-1]['value'] if data else None,
            'current_time': data[-1]['time'] if data else None,
        }
        return Response(return_data)


class NodeHeatGpuView(APIView):
    permission_classes = (AsUserRole,)

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
        category_mapping = {
            'memory': 'memory_util',
            'util': 'util',
            'temperature': 'temperature'
        }
        if category not in category_mapping:
            return Response(format_data)
        gpu_occupy_list = MonitorNode.objects.annotate(
            gpu_count=Count("gpu")).filter(
            gpu_count__gt=0
        ).values_list(
            'hostname', flat=True
        )
        nodes = sorted(set(nodelist).intersection(set(gpu_occupy_list)))
        if not nodes:
            format_data["offset"] = offset
            format_data["currentPage"] = currentPage
            return Response(format_data)
        ncnts = len(nodes)
        format_data["total"] = ncnts
        page_up_sum = offset * (currentPage - 1)
        start_idx = 0 if page_up_sum > ncnts else page_up_sum
        hostnames = nodes[start_idx:start_idx + offset]
        format_data["offset"] = offset
        format_data["currentPage"] = currentPage

        gpu_metric = category_mapping[category]
        metrics = \
            ['index', 'occupation', 'vendor', 'type', 'gpu_logical_device']
        metrics.append(gpu_metric)

        nodes_info = MonitorNode.objects.filter(
            hostname__in=hostnames
        ).as_dict(
            include=['gpu', 'hostname'],
            inspect_related=True,
            related_field_options=dict(
                gpu=dict(
                    include=metrics,
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
        for node_info in nodes_info:
            gpu_count = len(node_info['gpu'])
            if not gpu_count:
                format_data['nodes'].append({
                    'hostname': node_info['hostname'],
                    'value': [],
                    'used': [],
                    'vendor': [],
                    'product': [],
                    'logical_dev_info': []
                })
                continue

            gpu_dict = dict()
            gpu_dict['hostname'] = node_info['hostname']
            gpu_dev_metric = ['value', 'used', 'vendor', 'product']
            gpu_logical_metric = 'logical_dev_info'
            for dev_metric in gpu_dev_metric:
                gpu_dict[dev_metric] = [None] * gpu_count
            gpu_dict[gpu_logical_metric] = [list() for i in range(gpu_count)]
            parse_gpu_logical_info(node_info, gpu_dict, gpu_metric=gpu_metric)
            format_data['nodes'].append(gpu_dict)
        return Response(format_data)


class JobGpuBaseView(APIView):
    def generate_sql(self):
        sql = "select host,index,last(value) as value from gpu_metric " \
              "where metric = \'gpu_jobid\' and time > now() - 60s " \
              "group by host,index;"
        return sql

    def handle_query_data(self, data, job_id, result):
        data = data.get_points()
        for point in data:
            if job_id in point.get('value').split(','):
                if point['host'] in result:
                    result[point['host']].append(int(point['index']))
                else:
                    result[point['host']] = [int(point['index'])]

    def filter_host(self, result, hostlist=None):
        # Filter nodes that are not part of the cluster
        if not hostlist:
            hostlist = ClusterClient().get_hostlist()
        for hostname in list(result.keys()):
            if hostname not in hostlist:
                result.pop(hostname)


class JobGpuView(JobGpuBaseView):
    permission_classes = (AsUserRole,)

    def get(self, request, job_id):
        sql = self.generate_sql()
        result = {}
        try:
            data = InfluxClient().get(sql, epoch='s')
            self.handle_query_data(data, job_id, result)
            self.filter_host(result)
        except (InfluxDBServerError, InfluxDBClientError):
            logger.exception("Job %s gpu mapping failed.", job_id)
            raise InfluxDBException

        return Response(result)


class JobGpuHeatView(JobGpuBaseView):
    permission_classes = (AsUserRole,)

    def get_format_dict(self, request):
        format_data = {"currentPage": 0, "offset": 0, "total": 0, "nodes": []}
        currentPage = int(request.data["currentPage"])
        offset = int(request.data["offset"])
        nodelist = request.data["hostnames"]
        ncnts = len(nodelist)
        format_data["total"] = ncnts
        page_up_sum = offset * (currentPage - 1)
        start_idx = 0 if page_up_sum > ncnts else page_up_sum
        results = nodelist[start_idx:start_idx + offset]
        format_data["offset"] = offset
        format_data["currentPage"] = currentPage
        return format_data, results

    def get_job_node_info(self, job_nodes):
        """
            [
                {'hostname': 'c1', 'gpu': []},
                ...
            ]
        """
        gpu_node_list = MonitorNode.objects.filter(
            hostname__in=job_nodes
        ).annotate(
            hostnames=F('hostname')
        ).as_dict(
            include=['hostname', 'gpu'],
            inspect_related=True,
            related_field_options=dict(
                gpu=dict(
                    include=['type', 'gpu_logical_device', 'index', 'vendor'],
                    inspect_related=True,
                    related_field_options=dict(
                        logical_dev=dict(
                            include=('metric', 'value', 'dev_id'),
                            inspect_related=False
                        )
                    )
                )

            )
        )
        return gpu_node_list

    def get_job_gpu_type(self, gpu_node_list, job_nodes_dict):
        """
                {
                    'c1': {
                        '0-0': 'NVIDIA A100-PCIE-40GB / 3g.20gb',
                        '1': 'NVIDIA A100-PCIE-40GB'
                    }
                }

                """
        gpu_node_dict = defaultdict(dict)
        for node_info in gpu_node_list:
            hostname = node_info['hostname']
            for gpu_info in node_info['gpu']:
                index = str(gpu_info['index'])
                type_name = gpu_info['type']
                if index in job_nodes_dict[hostname]:
                    gpu_node_dict[hostname][index] = type_name
                    continue
                if not gpu_info['gpu_logical_device']:
                    continue
                for dev_info in gpu_info['gpu_logical_device']:
                    index_dev_id, dev_type_name = None, ''
                    if gpu_info['vendor'] == Gpu.INTEL:
                        index_dev_id = index + '-' + dev_info['dev_id']
                        dev_type_name = type_name + ' / ' + dev_info['dev_id']
                    elif gpu_info['vendor'] == Gpu.NVIDIA and \
                            dev_info['metric'] == 'name':
                        index_dev_id = index + '-' + \
                                       dev_info['dev_id'].split('.')[0]
                        dev_type_name = type_name + ' / ' + dev_info['value']
                    if index_dev_id is None or index_dev_id not in \
                            job_nodes_dict[hostname]:
                        continue
                    gpu_node_dict[hostname][index_dev_id] = dev_type_name
        return gpu_node_dict

    def parse_job_gpu_usage(self, gpu_job_info, host_list):

        """
            [
                {
                    'hostname': 'c1',
                    'index': '0-0',
                    'value': '100'
                },
                {
                    'hostname': 'c1',
                    'index': '1',
                    'value': '100'
                },
                {
                    'hostname': 'c2',
                    'index': '0-0',
                    'value': '100'
                },
                ...
            ]

           {
            'c1': [0-0, 1]
           }
        """
        job_nodes_dict, gpu_info_list = defaultdict(list), list()
        for gpu_dict in gpu_job_info.get_points():
            if gpu_dict['host'] not in host_list:
                continue
            gpu_info_dict = {}
            gpu_index = gpu_dict['gpu_id'] if not gpu_dict['dev_id'] else \
                gpu_dict['gpu_id'] + '-' + gpu_dict['dev_id'].split('.')[0]
            gpu_info_dict['index'] = gpu_index
            gpu_info_dict['hostname'] = gpu_dict['host']
            gpu_info_dict['value'] = round(float(gpu_dict['value']), 2)
            gpu_info_list.append(gpu_info_dict)
            job_nodes_dict[gpu_dict['host']].append(gpu_index)
        return job_nodes_dict, gpu_info_list

    def get_job_gpu_info(self, job_id, gpu_usage_metric):
        sql = "select host, gpu_id, dev_id, last(value) as value " \
              "from job_monitor_metric " \
              "where metric = $gpu_metric " \
              "and scheduler_id = $job_id " \
              "and time > now() - 1m group by host, gpu_id;"

        gpu_job_info = InfluxClient().get(
            sql, epoch='s', bind_params={
                "job_id": job_id,
                "gpu_metric": gpu_usage_metric
            }
        )
        return gpu_job_info

    def add_job_gpu_type(self, gpu_info_list, gpu_node_dict):
        for gpu_info in gpu_info_list:
            gpu_type = gpu_node_dict[gpu_info['hostname']][gpu_info['index']]
            gpu_info.update({'type': gpu_type})
        if gpu_info_list:
            gpu_info_list.sort(
                key=lambda x: (x['hostname'], str(x['index']))
            )

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
    def post(self, request, job_id, category):
        format_dict, host_list = self.get_format_dict(request)
        categroy_physics_mapping = {
            'memory': 'gpu_mem_usage',
            'util': 'gpu_util'
        }
        gpu_usage_metric = categroy_physics_mapping.get(category, None)
        if gpu_usage_metric is None:
            return Response(format_dict)

        gpu_job_info = self.get_job_gpu_info(job_id, gpu_usage_metric)

        if not gpu_job_info:
            return Response(format_dict)

        job_nodes_dict, gpu_info_list = \
            self.parse_job_gpu_usage(gpu_job_info, host_list)

        gpu_node_list = self.get_job_node_info(list(job_nodes_dict.keys()))

        gpu_node_dict = self.get_job_gpu_type(gpu_node_list, job_nodes_dict)

        self.add_job_gpu_type(gpu_info_list, gpu_node_dict)

        format_dict['nodes'].extend(gpu_info_list)
        return Response(format_dict)


class ClusterTendencyGpuView(ClusterTendencyBaseView):
    permission_classes = (AsOperatorRole,)

    def get_db_table(self):
        return 'nodegroup_metric'

    def get_db_metric(self):
        return 'gpu_util'


class ClusterTendencyGpuMemView(ClusterTendencyBaseView):
    permission_classes = (AsOperatorRole,)

    def get_db_table(self):
        return 'nodegroup_metric'

    def get_db_metric(self):
        return 'gpu_mem_usage'
