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
import re
from ast import literal_eval
from collections import defaultdict
from datetime import datetime

from django.conf import settings
from django.db.models import Count

from lico.core.monitor_host.models import (
    Cluster, MonitorNode, NodeSchedulableRes,
)
from lico.core.monitor_host.tasks.sync_latest import sync_latest
from lico.core.monitor_host.utils import (
    ClusterClient, InfluxClient, calculate_util, convert_unit,
    get_admin_scheduler, get_allocation_core, init_datasource,
)

logger = logging.getLogger(__name__)

NVIDIA = 0
INTEL = 1
AMD = 2

group_measurement = 'nodegroup_metric'
built_in_group = 'all'

node_metric_mapping = {
    'cpu_load': 'node_metric',
    'cpu_util': 'node_metric',
    'disk_util': 'node_metric',
    'memory_util': 'node_metric',
    'eth_in': 'node_metric',
    'eth_out': 'node_metric',
    'ib_in': 'node_metric',
    'ib_out': 'node_metric',
    'node_temp': 'node_metric',
    'node_power': 'node_metric',
    'node_active': 'node_metric',
    'node_health': 'node_metric',
    'hardware_discovery': 'node_metric'

}
job_metric_mapping = {
    'cpu_util': 'job_monitor_metric',
    'mem_used': 'job_monitor_metric',
    'gpu_util': 'job_monitor_metric',
    'gpu_mem_usage': 'job_monitor_metric',
    'mem_usage': 'job_monitor_metric'
}
gpu_metric_mapping = {
    'gpu_mem_usage': 'gpu_metric',
    'gpu_temp': 'gpu_metric',
    'gpu_util': 'gpu_metric',
    'gpu_util_mem': 'gpu_metric',
}
gpu_dev_metric_mapping = {
    'gpu_dev_util': 'gpu_logical_dev_metric',
    'gpu_dev_mem_usage': 'gpu_logical_dev_metric',
}
gpu_dev_tile_metric_mapping = {
    'gpu_dev_temp': 'gpu_logical_dev_metric',
    'gpu_dev_util_bandwidth': 'gpu_logical_dev_metric',
    'gpu_dev_util': 'gpu_logical_dev_metric',
    'gpu_dev_mem_usage': 'gpu_logical_dev_metric',
}


def _add_points(
        points, measurement, current, hostname, metric, value, **kwargs):
    point = {
        'measurement': measurement,
        'time': current,
        'tags': {
            'host': hostname,
            'metric': metric
        },
        'fields': {
            'value': value
        },
    }
    for key, value in kwargs.items():
        if value is not None:
            point['tags'][key] = value
    points.append(point)


def _calculate_mig_usage(gpu_data):
    gpu_dev_mem_usage = defaultdict(dict)
    gpu_dev_util = defaultdict(dict)
    mem_used_dict = gpu_data.gpu_metric.gpu_dev_model.gpu_dev_mem_used
    mem_total_dict = gpu_data.gpu_metric.gpu_dev_model.gpu_dev_mem_total
    proc_num_dict = gpu_data.gpu_metric.gpu_dev_model.gpu_dev_proc_num
    for index, total_list in mem_total_dict.items():
        gpu_dev_total_mem = defaultdict(int)
        for total_dict in total_list:
            dev_id = total_dict.get('dev_id')
            gpu_dev_total_mem[dev_id] = total_dict.get('value', '0.0')
        for used_dict in mem_used_dict.get(index, []):
            dev_id = used_dict['dev_id']
            used = used_dict.get('value', None)
            total = gpu_dev_total_mem[dev_id]
            if used is None or not float(total) or dev_id is None:
                continue
            gpu_dev_mem_usage[index][dev_id] = str(calculate_util(used, total))

    for index, proc_num_list in proc_num_dict.items():
        for proc_dict in proc_num_list:
            gpu_dev_util[index][proc_dict['dev_id']] = \
                '100' if float(proc_dict['value']) > 0.0 else '0'
    """
    gpu_dev_util or gpu_dev_mem_usage format for example:
    {
        '0': {
            '0.1.2': 100,
            '0.2.4': 0,
            ...
            },
        ...
    }
    """
    return gpu_dev_mem_usage, gpu_dev_util


def parse_nvidia_data(write_points, current, gpu_data):
    gpu_dev_mem_usage, gpu_dev_util = _calculate_mig_usage(gpu_data)
    gpu_mig_usage = locals()
    hostname = gpu_data.hostname
    for gpu_dev_metric, gpu_dev_measurement in gpu_dev_metric_mapping.items():
        gpu_dev_dict = gpu_mig_usage.get(gpu_dev_metric, defaultdict(dict))
        for index, dev_dict in gpu_dev_dict.items():
            for dev_id, value in dev_dict.items():
                _add_points(
                    write_points, gpu_dev_measurement, current, hostname,
                    gpu_dev_metric, value, gpu_id=index, dev_id=dev_id)


def format_tile_metric(tile_metric_dict):
    gpu_dev_tile_dict = defaultdict(dict)
    for index, tile_metric_list in tile_metric_dict.items():
        for tile_data in tile_metric_list:
            dev_id = tile_data['dev_id']
            gpu_dev_tile_dict[index][dev_id] = tile_data['value']
    return gpu_dev_tile_dict


def parse_intel_data(write_points, current, gpu_data):
    hostname = gpu_data.hostname
    mem_usage_dict = \
        gpu_data.gpu_metric.gpu_dev_model.gpu_dev_mem_usage
    util_dict = gpu_data.gpu_metric.gpu_dev_model.gpu_dev_util
    util_bandwidth_dict = \
        gpu_data.gpu_metric.gpu_dev_model.gpu_dev_util_bandwidth
    temp_dict = gpu_data.gpu_metric.gpu_dev_model.gpu_dev_temp
    gpu_dev_mem_usage = format_tile_metric(mem_usage_dict)
    gpu_dev_util = format_tile_metric(util_dict)
    gpu_dev_util_bandwidth = format_tile_metric(util_bandwidth_dict)
    gpu_dev_temp = format_tile_metric(temp_dict)

    for gpu_dev_metric, gpu_dev_measurement in \
            gpu_dev_tile_metric_mapping.items():
        gpu_dev_dict = locals().get(gpu_dev_metric, defaultdict())
        for index, dev_dict in gpu_dev_dict.items():
            for dev_id, value in dev_dict.items():
                _add_points(
                    write_points, gpu_dev_measurement, current, hostname,
                    gpu_dev_metric, value, gpu_id=index, dev_id=dev_id)


def parse_amd_data():
    pass


_add_gpu_points = {
    NVIDIA: parse_nvidia_data,
    INTEL: parse_intel_data,
    AMD: parse_amd_data
}


def _add_gpu_metric_points(write_points, current, gpu_data):
    """
    {'0':
        [
            {'dev_id': '', 'value': '98', 'unit': '', 'output': 'output...'},
            ...
        ]
    }
    """
    gpu_mem_usage = {}
    for index, value_list in gpu_data.gpu_metric.gpu_mem_total.items():
        total = value_list[0].get('value', 0)
        used = gpu_data.gpu_metric.gpu_mem_used.get(index, [])
        if not used or total == 0:
            continue
        gpu_mem_usage[index] = str(calculate_util(used[0]['value'], total))

    for gpu_metric, gpu_measurements in gpu_metric_mapping.items():
        if gpu_metric == 'gpu_mem_usage':
            for index, value in gpu_mem_usage.items():
                _add_points(
                    write_points, gpu_measurements, current, gpu_data.hostname,
                    gpu_metric, value=value, index=index)
            continue
        value_dict = getattr(
            gpu_data.gpu_metric, gpu_metric, defaultdict(list))
        if not value_dict:
            continue
        for index, gpu_list in value_dict.items():
            _add_points(
                write_points, gpu_measurements, current, gpu_data.hostname,
                gpu_metric, value=str(gpu_list[0]['value']), index=index)


def add_node_points(write_points, node_data, current):
    metric_unit = {
        'eth_in': 'MiB',
        'eth_out': 'MiB',
        'ib_in': 'MiB',
        'ib_out': 'MiB',
    }
    # {'value': '23', 'unit': '%', 'output': 'CPU Utiliztion = 10%, ...'}
    for node_metric, node_measurement in node_metric_mapping.items():
        value_dict = getattr(node_data.node_metric, node_metric, {})
        if not value_dict:
            continue
        value = value_dict['value']
        if node_metric in metric_unit:
            value, _ = convert_unit(
                value, value_dict['unit'], metric_unit[node_metric]
            )
        if node_metric == 'node_health':
            _, value = re.split(
                ' - ', literal_eval("'{}'".format(value_dict['output']))
            )
        _add_points(write_points, node_measurement, current,
                    node_data.hostname, node_metric, str(value))


def add_job_points(write_points, job_data, current):
    for job_metric, job_measurement in job_metric_mapping.items():
        value_dict = getattr(
            job_data.job_metric, job_metric, defaultdict(dict)
        )
        if not value_dict:
            continue
        for scheduler_id, scheduler_list in value_dict.items():
            for job_dict in scheduler_list:
                gpu_id = job_dict.get('index', None)
                dev_id = job_dict.get('dev_id', None)
                value = job_dict.get('value')
                if job_metric == 'mem_used':
                    unit = job_dict.get('unit', None)
                    value, _ = convert_unit(value, unit, 'kib')
                _add_points(
                    write_points, job_measurement, current, job_data.hostname,
                    job_metric, str(value), scheduler_id=scheduler_id,
                    gpu_id=gpu_id, dev_id=dev_id)


def add_gpu_points(write_points, gpu_data, current):
    # {'0': [{'dev_id': '', 'value': '98', 'output': 'output...'}, ..], ...}
    product_name_dict = getattr(
        gpu_data.gpu_metric, 'gpu_product_name', dict()
    )
    gpu_vender = None
    for index, vender_list in product_name_dict.items():
        gpu_vender = vender_list[0]['value']
        break
    if gpu_vender is None:
        return
    _add_gpu_metric_points(write_points, current, gpu_data)
    _add_gpu_points[int(float(gpu_vender))](write_points, current, gpu_data)


def add_hardware_points(write_points, hardware_data, current, hardware_old):
    if not hardware_old:
        return
    hardware_metric = ['disk_total', 'memory_total', 'cpu_socket_num',
                       'cpu_core_per_socket']
    unit_mapping = {
        'disk': 'gib',
        'memory': 'kib'
    }
    total_re = re.compile(r'^(disk|memory)_total$')
    hostname = hardware_data.hostname
    diff_metric = {}
    has_cpu_socket = False
    for metric in hardware_metric:
        metric_dict = getattr(hardware_data.node_metric, metric, {})
        new_value, new_unit = metric_dict.get('value'), metric_dict.get('unit')
        if metric == 'cpu_socket_num' and metric_dict:
            has_cpu_socket = True
        total_match = total_re.match(metric)
        if total_match:
            unit_metric = total_match.groups()[0]
            new_value, _ = \
                convert_unit(new_value, new_unit, unit_mapping[unit_metric])
        new_value = round(float(new_value), 2) if new_value else None
        old_value = float(hardware_old.get(metric))
        if new_value == old_value or new_value is None:
            continue
        diff_metric.update({
            metric + '_new': new_value,
            metric + '_old': old_value
        })
    gpu_total_new_value = getattr(
        hardware_data.gpu_metric, 'gpu_mem_total', {}
    )
    gpu_total_new = len(gpu_total_new_value) if has_cpu_socket else None
    gpu_total_old = hardware_old.get('gpu_total')

    if gpu_total_old != gpu_total_new and gpu_total_new is not None:
        diff_metric.update({
            'gpu_total_old': gpu_total_old,
            'gpu_total_new': gpu_total_new
        })
    if diff_metric:
        _add_points(
            write_points, 'node_metric', current, hostname,
            'hardware_discovery', json.dumps(diff_metric))


def get_hardware_old(compute_nodes):
    hardware_values = MonitorNode.objects.filter(
        hostname__in=compute_nodes
    ).annotate(
        gpu_total=Count('gpu')
    ).values(
        'disk_total', 'memory_total', 'cpu_socket_num',
        'cpu_core_per_socket', 'hostname', 'gpu_total'
    )
    hardware_dict = defaultdict(dict)
    for value_dict in hardware_values:
        hostname = value_dict.pop('hostname')
        hardware_dict[hostname] = value_dict
    """
        hardware_dict for format:
            {
                'c1': {
                    'disk_total': 7520.53,
                    'memory_total': 395559412.03,
                    'cpu_socket_num': 2,
                    'cpu_core_per_socket': 12,
                    'gpu_total': 2
                    },
                ...
            }
    """
    return hardware_dict


def summaries():
    current = datetime.utcnow()
    write_points = list()
    data_list = init_datasource()
    compute_nodes = [
        compute_node.hostname for compute_node in
        ClusterClient().get_nodelist() if compute_node.type == 'compute']
    hardware_old = get_hardware_old(compute_nodes)
    for node_data in data_list:
        try:
            add_node_points(write_points, node_data, current)
            add_job_points(write_points, node_data, current)
            add_gpu_points(write_points, node_data, current)
            add_hardware_points(write_points, node_data, current,
                                hardware_old[node_data.hostname])
        except Exception as e:
            message = 'Sync node {0} data exception! ' \
                      'Error message: {1}'.format(node_data.hostname, e)
            logger.exception(message)
    InfluxClient().set(write_points, retention_policy="hour")
    sync_latest(data_list)


def _get_group_node_info(nodes_obj, group_nodes):
    nodes_info = nodes_obj.filter(
        hostname__in=group_nodes
    ).as_dict(
        include=[
            'cpu_load', 'eth_in', 'eth_out', 'ib_in', 'hostname',
            'ib_out', 'power', 'disk_used', 'disk_total', 'cpu_util',
            'memory_used', 'memory_total', 'temperature', 'cpu_total'
        ]
    )
    node_util_metric = defaultdict(lambda: defaultdict(float))
    node_dict = defaultdict(float)
    temp_nodes = 0
    for node_info in nodes_info:
        hostname = node_info.pop('hostname')
        cpu_total = node_info.pop('cpu_total')
        metric_used = {
            'disk': node_info.pop('disk_used'),
            'memory': node_info.pop('memory_used')
        }
        for metric, value in node_info.items():
            if value is None:
                logging.warning(
                    'There is no {} in the {} node'.format(metric, hostname)
                )
                continue
            if metric == 'cpu_util':
                node_util_metric['cpu']['used'] += value * cpu_total / 100.0
                node_util_metric['cpu']['total'] += cpu_total
                continue
            if metric in ['disk_total', 'memory_total']:
                prefix, suffix = metric.split('_')
                if metric_used[prefix] is None:
                    continue
                node_util_metric[prefix][suffix] += value
                node_util_metric[prefix]['used'] += float(metric_used[prefix])
                continue
            if metric == 'temperature':
                temp_nodes += 1
            node_dict[metric] += float(value)
    temp = node_dict.pop('temperature', None)
    if temp is not None and temp_nodes:
        node_dict['temp'] = round(temp/temp_nodes, 2)
    return node_util_metric, node_dict


def add_write_points(nodes_obj, write_points, current, group, group_nodes):
    node_util_metric, node_dict = _get_group_node_info(nodes_obj, group_nodes)
    for metric, value_dict in node_util_metric.items():
        used = value_dict['used']
        total = value_dict['total']
        if total <= 0 or used < 0:
            logging.warning(
                'There is no {} in the {} groups'.format(metric, group)
            )
            continue
        _add_points(
            write_points, group_measurement, current, group,
            metric + '_' + 'util', round(100.0 * used / total, 2)
        )
    for metric, value in node_dict.items():
        _add_points(
            write_points, group_measurement, current, group, metric,
            float(value)
        )


def add_allocation_points(
        allocation_results, write_points, current, group, group_nodes):
    allocation_cores = 0.0
    for node in group_nodes:
        allocation_cores += allocation_results.get(node, 0.0)
    if group_nodes:
        _add_points(
            write_points, group_measurement, current, group,
            'allocating_core', float(allocation_cores)
        )


def add_cluster_points(write_points, current):
    cluster_metric = [
        'cpu_util', 'temperature', 'power', 'gpu_util', 'eth_in', 'eth_out',
        'ib_in', 'ib_out', 'disk_used', 'disk_total', 'memory_used',
        'memory_total', 'gpu_memory_used', 'gpu_memory_total'
    ]
    cluster_obj = Cluster.objects.filter(
        metric__in=cluster_metric
    ).as_dict(
        include=['metric', 'value']
    )

    cluster_util = defaultdict(dict)
    for cluster_metric in cluster_obj:
        metric = cluster_metric['metric']
        value = cluster_metric['value']
        if value is None:
            logging.warning('There is no {} in the cluster'.format(metric))
            continue
        if metric.endswith('_used') or metric.endswith('_total'):
            prefix, suffix = metric.rsplit('_', 1)
            cluster_util[prefix][suffix] = float(value)
            continue
        if metric == 'temperature':
            metric = 'temp'
        _add_points(
            write_points, group_measurement, current, built_in_group,
            metric, float(value)
        )

    for metric, value_dict in cluster_util.items():
        if len(value_dict) != 2:
            logger.warning('There is no {} in the cluster'.format(metric))
            continue
        used = float(value_dict['used'])
        total = float(value_dict['total'])
        if total <= 0 or used < 0:
            logger.warning(
                'There are no {0} in the cluster with a total or used '
                'value less than or equal to 0'.format(metric)
            )
            continue
        if metric.startswith('gpu'):
            _add_points(
                write_points, group_measurement, current, built_in_group,
                'gpu_mem_usage', round(100.0 * used / total, 2))
            continue
        _add_points(
            write_points, group_measurement, current, built_in_group,
            metric + '_' + 'util', round(100.0 * used / total, 2)
        )


def group_summaries():
    current = datetime.utcnow()
    '''
        group_nodes_dict:
        {
            'login': ['head', 'l1'],
            'head': ['head'],
            'compute': ['c1', 'c2', 'c3'],
            ...
        }
        '''
    write_points = []
    group_nodes_dict = defaultdict(list)
    for group in ClusterClient().get_nodegroup_nodelist():
        group_nodes_dict[group.name] = [node.hostname for node in group.nodes]
    nodes_obj = MonitorNode.objects
    allocation_results = get_allocation_core()
    for group, group_nodes in group_nodes_dict.items():
        add_write_points(nodes_obj, write_points, current, group, group_nodes)
        add_allocation_points(
            allocation_results, write_points, current, group, group_nodes
        )
    add_cluster_points(write_points, current)
    InfluxClient().set(write_points, retention_policy="hour")


_HOST_NODE_UTIL_SQL = """\
select last(value) as value, host, metric, scheduler_id
from job_monitor_metric
where metric=$metric and time > now() - {limit_time}
group by host, scheduler_id;"""


_HOST_METRICS_SQL = """\
select index, last(value) as value
from job_monitor_metric
where host=$host and metric=$metric and time > now() - {limit_time}
group by index;"""


def _get_cpu_mem_usage_info():
    host_cpu_util = defaultdict(lambda: defaultdict(float))
    host_mem_used = defaultdict(lambda: defaultdict(float))

    limit_time = settings.MONITOR.LIMIT_TIME
    cpu_util = InfluxClient().get(
        _HOST_NODE_UTIL_SQL.format(limit_time=limit_time),
        bind_params={"metric": "cpu_util"}
    )
    for item in cpu_util.get_points():
        host_cpu_util[item['host'].lower()] = {
            "host": item["host"],
            "value": float(item["value"]) + host_cpu_util[
                item['host'].lower()]["value"]
        }

    mem_used = InfluxClient().get(
        _HOST_NODE_UTIL_SQL.format(limit_time=limit_time),
        bind_params={"metric": "mem_used"}
    )
    for item in mem_used.get_points():
        host_mem_used[item['host'].lower()] = {
            "host": item["host"],
            "value": float(item["value"]) + host_mem_used[
                item['host'].lower()]["value"]
        }

    return host_cpu_util, host_mem_used


def _get_node_resource(node):
    cluster_node = MonitorNode.objects.ci_exact(
        hostname=node.get("hostname", ""))
    if cluster_node:
        if cluster_node[0].memory_total == 0:
            node["mem_total"] = node.get("mem_total", None)
            node["cpu_total"] = node.get("cpu_total", None)
        else:
            node["mem_total"] = node.get("mem_total", None) or cluster_node[
                0].memory_total
            node["cpu_total"] = node.get("cpu_total", None) or cluster_node[
                0].cpu_total
    else:
        logger.warning("This node unmonitored: {}".format(
            node.get("hostname", "")))


def _get_gres_data(host, metrics_mapping):
    """
    :return:
    {
        metrics_1: [(0, 10), (1, 20)],
    }
    """
    metrics, metrics_key = metrics_mapping

    metrics_value = InfluxClient().get(
        _HOST_METRICS_SQL.format(limit_time=settings.MONITOR.LIMIT_TIME),
        bind_params={"host": host,
                     "metric": metrics_key}
    ).get_points()
    metrics_value = sorted(list(metrics_value), key=lambda x: x["index"])

    return {
        metrics: [(item["index"], item["value"]) for item in metrics_value]
    }


def cluster_res_summaries():
    """
    influxDB + scheduler -> mysql
    :return:
    """
    scheduler = get_admin_scheduler()

    # [{
    #     "hostname": "lico-c1",
    #     "state": "ok",
    #     "cpu_total": 64,
    #     "mem_total": 300000,
    #     "gres": {
    #         "gpu": {
    #             "total": 2
    #         },
    #         "gpfs": {
    #             "total": 1
    #         }
    #     }
    # },]
    scheduler_res = scheduler.get_scheduler_resource()
    # {'gpu': [['util', 'gpu_util'], [, ]]}
    gres_mapping = settings.MONITOR.GRES
    # {"lsf2-1": {"host": "LSF2-1", "value": 2.0}}
    host_cpu_util, host_mem_used = _get_cpu_mem_usage_info()

    scheduler_hosts = list()
    for node in scheduler_res:
        node['cpu_util'] = 0
        node['mem_used'] = 0
        rel_host = None

        _get_node_resource(node)

        if node.get("hostname", "").lower() in host_cpu_util:
            node['cpu_util'] = host_cpu_util[
                node.get("hostname", "").lower()]["value"]
            rel_host = host_cpu_util[
                node.get("hostname", "").lower()]["host"]

        if node.get("hostname", "").lower() in host_mem_used:
            node['mem_used'] = host_mem_used[
                node.get("hostname", "").lower()]["value"]
            rel_host = host_mem_used[
                node.get("hostname", "").lower()]["host"]

        for k, v in node.get("gres", {}).items():
            for metrics_mapping in gres_mapping.get(k, []):
                metrics_data = _get_gres_data(
                    node.get("hostname"), metrics_mapping
                )
                # {
                #     metrics_1: [(0, 10), (1, 20)],
                # }
                v.update(metrics_data)

        node["gres"] = json.dumps(node.get("gres", {}))

        if rel_host is not None:
            node["hostname"] = rel_host

        scheduler_hosts.append(node.get("hostname"))

        node_res = NodeSchedulableRes.objects.ci_exact(
            hostname=node["hostname"])

        if len(node_res) > 0:
            node_res.update(**node)
        else:
            NodeSchedulableRes.objects.create(**node)

    NodeSchedulableRes.objects.exclude(hostname__in=scheduler_hosts).delete()

