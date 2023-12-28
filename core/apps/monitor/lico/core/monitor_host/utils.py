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
import os
import re
from collections import defaultdict

import attr
import requests
import xmltodict
from django.conf import settings
from django.db.models import Q

from lico.core.contrib.client import Client

from .dataclass import ResData, ResUtilization
from .exceptions import CheckPreferenceException, UsernamePasswordNotSet
from .models import Gpu, MonitorNode, NodeSchedulableRes, Preference

logger = logging.getLogger(__name__)

NODE_TYPES = ['head', 'login', 'compute', 'service', 'gpu', 'io']
IDLE_THRESHOLD = 20
BUSY_THRESHOLD = 80


class DataSourceInfluxClient(object):

    def __init__(self):
        from lico.password import fetch_pass
        username, password = fetch_pass('datasource')
        if username is None or password is None:
            warning_message = \
                'Datasource account username or password not exists!'
            logger.warning(warning_message)

        from influxdb import InfluxDBClient
        self._client = InfluxDBClient(
            host=settings.MONITOR.DATASOURCE.INFLUX.host,
            database=settings.MONITOR.DATASOURCE.INFLUX.database,
            username=username,
            password=password
        )

    def get(self, sql, **kwargs):
        return self._client.query(sql, **kwargs)

    def set(self, json, **kwargs):
        return self._client.write_points(json, **kwargs)

    def delete_series(self, measurement=None, tags=None):
        return self._client.delete_series(measurement=measurement, tags=tags)


class InfluxClient(object):  # pragma: no cover
    def __init__(self):
        from lico.core.contrib.client import Client
        self._client = Client().influxdb_client()

    def get(self, sql, default=None, version=None, **kwargs):
        return self._client.query(sql, **kwargs)

    def set(self, json, default=None, version=None, **kwargs):
        return self._client.write_points(json, **kwargs)

    def delete_series(self, measurement=None, tags=None):
        return self._client.delete_series(measurement=measurement, tags=tags)


class ClusterClient(object):  # pragma: no cover
    def __init__(self):
        from lico.core.contrib.client import Client
        self._client = Client().cluster_client()

    def get_group_nodelist(self, groupname):
        nodelist = [group.nodes
                    for group in self._client.get_group_nodelist()
                    if group.name == groupname]
        return [{'hostname': node.hostname}
                for node in nodelist[0]] if nodelist else []

    def get_nodelist(self):
        return self._client.get_nodelist()

    def get_hostlist(self):
        return self._client.get_hostlist()

    def get_row_racklist(self):
        return self._client.get_row_racklist()

    def get_rack_nodelist(self, racks=[]):
        return self._client.get_rack_nodelist(racks)

    def get_nodegroup_nodelist(self):
        return self._client.get_group_nodelist()


def str_to_float(value):
    try:
        value = round(float(value), 2)
    except Exception:
        logger.warn('Invalid float format: %s', value)
    finally:
        return value


def convert_value(data, key='value'):
    data[key] = str_to_float(data[key])
    return data


def get_node_status_preference(user):
    logger.info("Get preference for node status")
    name = "monitor_host.policy.node.status"
    try:
        preference = Preference.objects.get(name=name)
    except Preference.DoesNotExist as e:
        logger.exception('Preference name %s does not exist', name)
        raise CheckPreferenceException from e
    else:
        if preference.username in [None, user.username]:
            # 'cpu_core' or 'cpu_util' for value
            return preference.value
        else:
            return "cpu_util"


def get_node_status(
        preference, hostname=None, cpu_util=None, to_lowercase=True):
    if preference == "cpu_util":
        if cpu_util is None:
            cpu_util = -1
        if cpu_util > BUSY_THRESHOLD:
            status = "busy"
        elif cpu_util < IDLE_THRESHOLD:
            status = "idle"
        else:
            status = "used"
    else:
        busy_nodes = node_check(to_lowercase=to_lowercase)
        if hostname is not None and hostname.lower() in busy_nodes:
            status = "busy"
        else:
            status = "idle"
    return status


def get_node_statics(preference, nodelist):
    lens = len(NODE_TYPES)

    off = [0] * lens
    busy = [0] * lens
    used = [0] * lens
    idle = [0] * lens

    result = {
        "state": {
            "occupied": used,
            "idle": idle,
            "busy": busy,
            "off": off
        },
        "types": NODE_TYPES
    }
    for node_type in NODE_TYPES:
        host_list = [node.hostname
                     for node in nodelist
                     if node.type == node_type]
        total = MonitorNode.objects.filter(hostname__in=host_list)
        # node state is off by default when cluster node monitor info
        # can't be inserted into MonitorNode.
        extra_off_node = len(host_list) - total.count()
        if preference == "cpu_util":
            off_cnt = total.filter(
                node_active=False
            ).count()
            busy_cnt = total.filter(
                node_active=True,
                cpu_util__gt=BUSY_THRESHOLD
            ).count()
            idle_cnt = total.filter(
                node_active=True,
                cpu_util__lt=IDLE_THRESHOLD
            ).count()
            used_cnt = total.count() - off_cnt - busy_cnt - idle_cnt

            off_cnt += extra_off_node

            idx = NODE_TYPES.index(node_type)
            off[idx] = off_cnt
            busy[idx] = busy_cnt
            idle[idx] = idle_cnt
            used[idx] = used_cnt
        else:
            on_nodes = total.filter(node_active=True).values_list(
                'hostname', flat=True
            )
            off_cnt = total.count() - len(on_nodes)
            busy_cnt = len(set(on_nodes) & node_check())
            used_cnt = 0
            idle_cnt = total.count() - off_cnt - busy_cnt - used_cnt

            off_cnt += extra_off_node

            idx = NODE_TYPES.index(node_type)
            off[idx] = off_cnt
            busy[idx] = busy_cnt
            idle[idx] = idle_cnt
            used[idx] = used_cnt

    return result


def node_check(to_lowercase=False) -> set:  # pragma: no cover
    """
    return all node that carry running job
    :return: {'c1', 'c2'...}
    """
    from lico.core.contrib.client import Client
    job_client = Client().job_client()
    result = job_client.get_host_resource_used()
    if to_lowercase:
        nodes = {
            key.lower() for key in result.keys()
            if result[key]['runningjob_num']
        }
    else:
        nodes = {
            key for key in result.keys()
            if result[key]['runningjob_num']
        }
    return nodes


class ResourceFactory:
    def __init__(self):
        self.res_class = {
            'cluster': ClusterResource,
            'scheduler': SchedulerResource
        }

    def get_res(self, restype):
        return self.res_class[restype]().get_data()


class MonitorResource:
    def make_obj(self, node, obj, gpu_info=None):

        if isinstance(self, ClusterResource):
            obj.data['hypervisor_vendor'].append(
                ResUtilization(
                    1 if node.hypervisor_vendor else 0,
                )
            )
            obj.data['sockets'].append(
                ResUtilization(
                    node.cpu_socket_num,
                )
            )
            obj.data['cpu'].append(
                ResUtilization(
                    node.cpu_total,
                    node.cpu_util
                )
            )
            obj.data['mem'].append(
                ResUtilization(
                    node.memory_total,
                    node.memory_used
                )
            )
            for gpu_index, info in gpu_info[node.hostname].items():
                obj.data[self.gres_gpu_code].append(
                    ResUtilization(
                        usage=info['util'],
                        index=gpu_index)
                )
                obj.data[f'{self.gres_gpu_code}_mem'].append(
                    ResUtilization(
                        info['memory_total'],
                        info['memory_util'],
                        index=gpu_index
                    )
                )
                obj.data[f'{self.gres_gpu_code}_mig_mode'].append(
                    ResUtilization(
                        total=info['mig_device_num'],
                        usage=info['mig_mode'],
                        index=gpu_index
                    )
                )

        if isinstance(self, SchedulerResource):
            if node.cpu_total is None or node.cpu_util is None:
                cpu_util = None
            else:
                cpu_util = node.cpu_util / node.cpu_total
            obj.data['cpu'].append(
                ResUtilization(
                    node.cpu_total,
                    cpu_util
                )
            )
            obj.data['mem'].append(
                ResUtilization(
                    node.mem_total,
                    node.mem_used
                )
            )
            for gk, gv in json.loads(node.gres).items():
                # will modify when add gpfs
                total, util = int(gv.get('total', 0)), gv.get('util', [])
                util.extend([(0, 0)] * (max(total, len(util)) - len(util)))
                for _index, g in enumerate(util):
                    obj.data[gk].append(
                        ResUtilization(
                            usage=float(g[1]),
                            index=_index
                        )
                    )


class ClusterResource(MonitorResource):
    def __init__(self):
        self.gres_gpu_code = settings.MONITOR.CLUSTER_GRES.get('Gpu')

    def get_gpu_info(self):
        gpu_info = defaultdict(lambda: defaultdict(dict))
        if self.gres_gpu_code is not None:
            for gpu in Gpu.objects.all().as_dict(
                    include=['monitor_node', 'index', 'util', 'memory_total',
                             'memory_util', 'mig_mode', 'gpu_logical_device'],
            ):
                gpu_logical_dev = set()
                for dev_dict in gpu['gpu_logical_device']:
                    gpu_logical_dev.add(dev_dict['dev_id'])
                gpu_info[gpu['monitor_node']['hostname']][gpu['index']].update(
                    {
                        'util': gpu['util'],
                        'memory_total': gpu['memory_total'],
                        'memory_util': gpu['memory_util'],
                        'mig_mode': gpu['mig_mode'],
                        'mig_device_num': len(gpu_logical_dev)
                    }
                )
        return gpu_info

    def get_data(self):
        res = []
        gpu_info = self.get_gpu_info()
        for node in MonitorNode.objects.iterator():
            resdata = ResData(
                node.hostname,
                node.node_active,
                defaultdict(list)
            )
            self.make_obj(node, resdata, gpu_info)
            res.append(resdata.to_dict())
        return res


class SchedulerResource(MonitorResource):

    def get_data(self):
        res = []
        for node in NodeSchedulableRes.objects.iterator():
            resdata = ResData(
                node.hostname,
                node.state,
                defaultdict(list)
            )
            self.make_obj(node, resdata)
            res.append(resdata.to_dict())
        return res


class IcingaDataSource:
    def __init__(self, api_v="v1"):
        from lico.password import fetch_pass
        icinga_user, icinga_password = fetch_pass('icinga')
        if icinga_user is None or icinga_password is None:
            raise UsernamePasswordNotSet('Icinga')
        icinga_conf = settings.MONITOR.ICINGA
        self.host = icinga_conf['host']
        self.port = icinga_conf['port']
        self.timeout = icinga_conf['timeout']
        self.headers = {
            "Accept": "application/json"
        }
        self.auth = (icinga_user, icinga_password)
        self.api_v = api_v

    def get_procs_data(self, hostname):
        attrs = self.fetch_service_data('lico-procs-service', hostname)
        if attrs.get("problem"):
            return ""
        check_result = attrs.get("last_check_result")
        return check_result.get("output", "") if check_result else ""

    def get_job_data(self, hostname):
        attrs = self.fetch_service_data('lico-job-service', hostname)
        if attrs.get("problem"):
            return []
        return attrs.get("last_check_result", {}).get("performance_data", [])

    def scheduler_service(self, service_pattern, hostname):
        filter_ = f'match(\"{service_pattern}\",service.name)&&' \
                  f'host.name==\"{hostname}\"'
        res = requests.post(
            url="https://{0}:{1}/{2}/actions/reschedule-check".format(
                self.host, self.port, self.api_v
            ),
            headers=self.headers,
            auth=self.auth,
            json={
                "type": "Service",
                "filter": filter_,
                "force": "true"
            },
            verify=False,  # nosec B501
            timeout=self.timeout
        )
        if res.status_code != 200:
            res.raise_for_status()

    def fetch_service_data(self, service, hostname):
        res = requests.get(
            url="https://{0}:{1}/{2}/objects/services/{3}!{4}".format(
                self.host, self.port, self.api_v, hostname, service
            ),
            headers=self.headers,
            auth=self.auth,
            params={"attrs": ["last_check_result", "problem"]},
            verify=False,  # nosec B501
            timeout=self.timeout
        )
        if res.status_code != 200:
            res.raise_for_status()
        return res.json().get("results", [{}])[0].get("attrs", {})


def get_admin_scheduler():
    if settings.LICO.SCHEDULER == 'slurm':
        from lico.scheduler.adapter.scheduler_factory import (
            create_slurm_scheduler as create_scheduler,
        )
    elif settings.LICO.SCHEDULER == 'lsf':
        from lico.scheduler.adapter.scheduler_factory import (
            create_lsf_scheduler as create_scheduler,
        )
    elif settings.LICO.SCHEDULER == 'pbs':
        from lico.scheduler.adapter.scheduler_factory import (
            create_pbs_scheduler as create_scheduler,
        )

    return create_scheduler('root')


# result_set_lists format:
#   [
#      ResultSet({
#          '('test', None)': [
#                {'time': 1615842000, 'host': 'c10',
#                'metric': 'cpu_util', 'value': '0'},
#                ....
#           ]}),
#      ResultSet({
#          '('test', None)': [
#                {'time': 1615842000, 'host': 'c10',
#                'metric': 'cpu_util', 'value': '0'},
#                ....
#           ]}),
#   ]
# default params values: head, end. The values default all
#   head: Only take data with the same beginning timestamp
#   end: Only take data with the same ending timestamp
def align_data(result_set_lists, head=True, end=True):
    result_set1, result_set2 = result_set_lists
    no_data = list()
    if not result_set1 or not result_set2:
        return no_data
    result1 = list(result_set1.get_points())
    result2 = list(result_set2.get_points())
    res_head_time1 = result1[0]['time']
    res_head_time2 = result2[0]['time']
    res_end_time1 = result1[-1]['time']
    res_end_time2 = result2[-1]['time']

    # No overlapping data
    if res_head_time1 > res_end_time2 or res_end_time1 < res_head_time2:
        return no_data

    # split time for get the critical value
    res_head_time = \
        res_head_time1 if res_head_time1 >= res_head_time2 else res_head_time2
    res_end_time = \
        res_end_time1 if res_end_time1 <= res_end_time2 else res_end_time2

    if head:
        result1 = _cut_data(res_head_time, result1)
        result2 = _cut_data(res_head_time, result2)
    if end:
        result1 = _cut_data(res_end_time, result1, factor=-1)
        result2 = _cut_data(res_end_time, result2, factor=-1)
    return result1, result2


# factor: default 1, else -1
#   1: Only take data with the same beginning timestamp
#   -1: Only take data with the same ending timestamp
def _cut_data(res_time, result_list, factor=1):
    index = 0 if factor == 1 else 1
    while result_list[index * factor]['time'] != res_time:
        index += 1
    if factor == 1:
        return result_list[index:]
    return result_list if index == 1 else result_list[:index * factor + 1]


def second2str(seconds: int) -> str:
    day, hour, minute = 24 * 60 * 60, 60 * 60, 60
    time_str = ""
    if seconds > day:
        days, seconds = divmod(seconds, day)
        time_str += "%dd" % days
    if seconds > hour:
        hours, seconds = divmod(seconds, hour)
        time_str += "%dh" % hours
    if seconds > minute:
        mins, seconds = divmod(seconds, minute)
        time_str += "%dm" % mins
    if seconds > 0:
        time_str += "%ds" % seconds
    return time_str


def str2second(t: str) -> int:
    import re
    secs = 0
    time_re = {
        "s": r"([\d]+)s",
        "m": r"([\d]+)m",
        "h": r"([\d]+)h",
        "d": r"([\d]+)d",
        "w": r"([\d]+)w",
    }

    time_mapping = {
        "s": 1,
        "m": 60,
        "h": 60 * 60,
        "d": 24 * 60 * 60,
        "w": 7 * 24 * 60 * 60,
    }

    for k, v in time_re.items():
        r = re.search(v, t)
        if r:
            secs += time_mapping[k] * int(r.groups()[0])

    return secs


def get_new_time_rule(interval_time: str, category_time: str,
                      factor: float = 0.1
                      ) -> (str, int):
    if "EXPANSION_FACTOR" in settings.MONITOR:
        conf_factor = settings.MONITOR.EXPANSION_FACTOR
        if isinstance(conf_factor, float) or isinstance(conf_factor, int):
            factor = conf_factor

    interval = str2second(interval_time)
    time_limit = str2second(category_time)
    span = time_limit / interval
    new_span = span * (1 + factor)
    new_time_limit = second2str(int(new_span * interval))
    return new_time_limit, int(span)


def cut_list(data: list, start: int = None, end: int = None,
             max_len: int = None, cut_from_start=True) -> list:
    if start is not None:
        data = data[start:]
    if end is not None:
        data = data[:end]
    if max_len is not None:
        if cut_from_start:
            data = data[:max_len]
        else:
            data = data[-max_len:]
    return data


NODE_ON, NODE_OFF = 'UP', 'DOWN'
job_re = re.compile(r'^job_([0-9a-zA-Z]*)_(cpu_util|mem_used)$')
node_re = re.compile(r'^(vnc_session)_\d+|(node_health)_critical_count$')
gpu_re = re.compile(
    r'^(gpu)(\d+)_(driver|product_name|uuid|pcie_generation|util|temp|'
    r'mem_used|mem_total|proc_num|util_mem|mig_mode)$')
gpu_dev_re = re.compile(
    r'^(gpu)(\d+)_(.*)_(util|mem_used|mem_total|proc_num|util_bandwidth|'
    r'mem_usage|sm_count|temp)$')
job_gpu_re = re.compile(
    r'^job_([0-9a-zA-Z]*)_(gpu)(\d+)(.*)_(util|mem_usage)$')

_SQL = """
SELECT hostname, metric, output_data as output, LAST(value) as value, unit
FROM {measurement} WHERE time > now() - 1m GROUP BY hostname, metric;
"""

# Node switch on/off data is reported every 5 minutes
# so the latest value within 10 minutes is obtained
_NODE_ACTIVE_SQL = """
SELECT hostname, metric, state as output, LAST(value) as value, unit
FROM hostalive WHERE time > now() - 10m GROUP BY hostname, metric;
"""


def calculate_util(used, total):
    return round(100.0 * float(used) / float(total), 2)


def convert_unit(value, unit, target_unit='BYTES'):
    unit_mapping = {
        'BITS': 2.0 ** -3,
        'BYTES': 1.0,
        'KB': 1000.0 ** 1,
        'MB': 1000.0 ** 2,
        'GB': 1000.0 ** 3,
        'TB': 1000.0 ** 4,
        'PB': 1000.0 ** 5,
        'EB': 1000.0 ** 6,
        'ZB': 1000.0 ** 7,
        'YB': 1000.0 ** 8,

        'KIB': 1024.0 ** 1,
        'MIB': 1024.0 ** 2,
        'GIB': 1024.0 ** 3,
        'TIB': 1024.0 ** 4,
        'PIB': 1024.0 ** 5,
        'EIB': 1024.0 ** 6,
        'ZIB': 1024.0 ** 7,
        'YIB': 1024.0 ** 8,
    }
    if not unit or not unit_mapping.get(unit.upper()) or \
            not unit_mapping.get(target_unit.upper()):
        return value, unit
    value_bytes = float(value) * unit_mapping[unit.upper()]
    return value_bytes / unit_mapping[target_unit.upper()], target_unit


@attr.s(frozen=True)
class NodeMetric:
    cpu_util = attr.ib(default=attr.Factory(dict))
    cpu_load = attr.ib(default=attr.Factory(dict))
    cpu_socket_num = attr.ib(default=attr.Factory(dict))
    cpu_core_per_socket = attr.ib(default=attr.Factory(dict))
    cpu_thread_per_core = attr.ib(default=attr.Factory(dict))
    memory_used = attr.ib(default=attr.Factory(dict))
    memory_total = attr.ib(default=attr.Factory(dict))
    memory_util = attr.ib(default=attr.Factory(dict))
    disk_util = attr.ib(default=attr.Factory(dict))
    disk_used = attr.ib(default=attr.Factory(dict))
    disk_total = attr.ib(default=attr.Factory(dict))
    eth_in = attr.ib(default=attr.Factory(dict))
    eth_out = attr.ib(default=attr.Factory(dict))
    ib_in = attr.ib(default=attr.Factory(dict))
    ib_out = attr.ib(default=attr.Factory(dict))
    node_temp = attr.ib(default=attr.Factory(dict))
    node_power = attr.ib(default=attr.Factory(dict))
    node_active = attr.ib(default=attr.Factory(dict))
    node_health = attr.ib(default=attr.Factory(dict))
    hypervisor_mode = attr.ib(default=attr.Factory(dict))
    vnc_session = attr.ib(default=attr.Factory(dict))


@attr.s(frozen=True)
class GpuLogicMetric:
    """
        format for example:
            {
                '0': [
                        {
                            'dev_id': '0.1.2',
                            'value': '98',
                            'output': 'output...',
                            'unit': ''},
                        ..
                    ],
            ...
            }
        dev_id:
            for nvidia: '<device_id.gi_id.ci_id>'
            for intel: '<tile_id>'
    """
    gpu_dev_spec = attr.ib(
        default=attr.Factory(lambda: defaultdict(list)))
    gpu_dev_mem_used = attr.ib(
        default=attr.Factory(lambda: defaultdict(list)))
    gpu_dev_proc_num = attr.ib(
        default=attr.Factory(lambda: defaultdict(list)))
    gpu_dev_mem_total = attr.ib(
        default=attr.Factory(lambda: defaultdict(list)))  # nvidia
    gpu_dev_sm_count = attr.ib(
        default=attr.Factory(lambda: defaultdict(list)))  # nvidia
    gpu_dev_util_bandwidth = attr.ib(
        default=attr.Factory(lambda: defaultdict(list)))  # intel
    gpu_dev_mem_usage = attr.ib(
        default=attr.Factory(lambda: defaultdict(list)))  # intel
    gpu_dev_util = attr.ib(
        default=attr.Factory(lambda: defaultdict(list)))  # intel
    gpu_dev_temp = attr.ib(
        default=attr.Factory(lambda: defaultdict(list)))  # intel


@attr.s(frozen=True)
class GpuPhysicsMetric:
    """
        format for example:
            {
                '0': [
                        {
                            'dev_id': None,
                            'value': '98',
                            'output': 'output...',
                            'unit': ''},
                        ..
                    ],
            ...
            }
    """
    gpu_util = attr.ib(default=attr.Factory(lambda: defaultdict(list)))
    gpu_temp = attr.ib(default=attr.Factory(lambda: defaultdict(list)))
    gpu_mem_used = attr.ib(default=attr.Factory(lambda: defaultdict(list)))
    gpu_mem_total = attr.ib(default=attr.Factory(lambda: defaultdict(list)))
    gpu_proc_num = attr.ib(default=attr.Factory(lambda: defaultdict(list)))
    gpu_util_mem = attr.ib(default=attr.Factory(lambda: defaultdict(list)))
    gpu_product_name = attr.ib(default=attr.Factory(lambda: defaultdict(list)))
    gpu_uuid = attr.ib(default=attr.Factory(lambda: defaultdict(list)))
    gpu_driver = attr.ib(default=attr.Factory(lambda: defaultdict(list)))
    gpu_mig_mode = attr.ib(default=attr.Factory(lambda: defaultdict(list)))
    gpu_dev_model = attr.ib(default=attr.Factory(lambda: GpuLogicMetric()))
    gpu_pcie_generation = attr.ib(
        default=attr.Factory(lambda: defaultdict(list)))


@attr.s(frozen=True)
class JobMetric:
    """
    format for example:
        {
            '<scheduler_id>': [
                    {
                        'value': '98',
                        'output': 'output...',
                        'dev_id': None,
                        'index': None,
                        'unit': ''
                        },
                    ..
                ],
        ...
        }
    """
    cpu_util = attr.ib(default=attr.Factory(lambda: defaultdict(list)))
    mem_used = attr.ib(default=attr.Factory(lambda: defaultdict(list)))
    mem_usage = attr.ib(default=attr.Factory(lambda: defaultdict(list)))
    gpu_util = attr.ib(default=attr.Factory(lambda: defaultdict(list)))
    gpu_mem_usage = attr.ib(default=attr.Factory(lambda: defaultdict(list)))


class NodesInfo:
    def __init__(self, hostname, node_metric, gpu_metric, job_metric):
        self.hostname = hostname
        self.node_metric = node_metric
        self.gpu_metric = gpu_metric
        self.job_metric = job_metric


def set_job_attr(metric, job_info, value_dict, memory_total=0):
    value, output, unit = \
        value_dict['value'], value_dict['output'], value_dict['unit']

    job_match = job_re.match(metric)
    if job_match:
        scheduler_id, metric_name = job_match.groups()
        job_dict = getattr(job_info, metric_name, defaultdict(list))
        index = dev_id = None
        if metric_name == 'mem_used' and memory_total != 0:
            job_mem_usage = getattr(
                job_info, 'mem_usage', defaultdict(list)
            )
            mem_usage = str(round(float(value) / float(memory_total), 2))
            job_mem_usage[scheduler_id].append(
                {'value': mem_usage, 'output': '', 'index': index,
                 'dev_id': dev_id, 'unit': unit})
        job_dict[scheduler_id].append(
            {'value': value, 'output': output, 'index': index,
             'dev_id': dev_id, 'unit': unit})
        return

    job_gpu_match = job_gpu_re.match(metric)
    if not job_gpu_match:
        return
    scheduler_id, gpu_str, index, dev_str, gpu_metric_name = \
        job_gpu_match.groups()
    gpu_metric = gpu_str + '_' + gpu_metric_name
    dev_id = dev_str[1:].replace('_', '.') if dev_str else ''
    gpu_job_dict = getattr(job_info, gpu_metric, defaultdict(list))
    gpu_job_dict[scheduler_id].append({
        'index': index,
        'dev_id': dev_id,
        'value': value,
        'output': output,
        'unit': unit}
    )


def set_gpu_attr(metric, gpu_info, value_dict):
    value, output, unit = \
        value_dict['value'], value_dict['output'], value_dict['unit']
    gpu_match = gpu_re.match(metric)

    if gpu_match:
        gpu_str, index, metric_name = gpu_match.groups()
        gpu_metric = gpu_str + '_' + metric_name
        gpu_dict = getattr(gpu_info, gpu_metric, defaultdict(list))
        gpu_metric_dict = \
            {'value': value, 'output': output, 'dev_id': None, 'unit': unit}
        gpu_dict[index].append(gpu_metric_dict)
        return

    gpu_dev_match = gpu_dev_re.match(metric)
    if gpu_dev_match:
        gpu_dev_model = gpu_info.gpu_dev_model
        gpu_str, index, dev_str, gpu_metric_name = gpu_dev_match.groups()
        metric_name = gpu_str + '_dev_' + gpu_metric_name
        gpu_dev_dict = getattr(gpu_dev_model, metric_name, defaultdict(list))
        dev_id = dev_str.replace('_', '.')
        gpu_dev_metric_dict = \
            {'value': value, 'output': output, 'dev_id': dev_id, 'unit': unit}
        gpu_dev_dict[index].append(gpu_dev_metric_dict)
        return

    gpu_spec_re = re.compile(r'(gpu)(\d+)_([\d+_]*)$')
    gpu_spec_match = gpu_spec_re.match(metric)
    if gpu_spec_re:
        gpu_dev_model = gpu_info.gpu_dev_model
        gpu_str, index, dev_str = gpu_spec_match.groups()
        gpu_dev_metric = gpu_str + '_dev_spec'
        gpu_dict = getattr(gpu_dev_model, gpu_dev_metric, defaultdict(list))
        dev_id = dev_str.replace('_', '.')
        get_dev_dict = \
            {'dev_id': dev_id, 'value': value, 'output': output, 'unit': unit}
        gpu_dict[index].append(get_dev_dict)


def set_node_attr(metric, node_info, value_dict):
    node_re_match = node_re.match(metric)
    if not node_re_match:
        getattr(node_info, metric, {}).update(value_dict)
        return
    for node_metric in node_re_match.groups():
        if node_metric:
            getattr(node_info, node_metric, {}).update(value_dict)


def _generator_sql():
    influx_sql = ';'
    for measurement in settings.MONITOR.DATASOURCE.INFLUX.measurements:
        influx_sql += _SQL.format(measurement=measurement)
    return influx_sql + _NODE_ACTIVE_SQL


def _init_datasource(metrics_dict):
    for calculate_metric in ['disk_total', 'memory_total']:
        metric_match = re.match(r'^(disk|memory)_total$', calculate_metric)
        metric_str = metric_match.groups()[0]
        # total_dict for example:
        # {
        #     'value': '0.0', 'unit': 'BYTES',
        #     'output': '[OK] - Disk total = 0.0B, Disk used = 0.0B '
        # }
        total = metrics_dict.get(calculate_metric, {}).get('value', None)
        used = metrics_dict.get(metric_str + '_used', {}).get('value', None)
        if total is None or used is None:
            continue
        metrics_dict[metric_str + '_util'] = {
            'value': '0.0' if int(float(total)) == 0 else str(
                calculate_util(used, float(total))),
            'unit': '%', 'output': ''}
    state_list = []
    for active_metric in ['rta', 'pl']:
        active_metric_dict = metrics_dict.pop(active_metric, {})
        if not active_metric_dict:
            continue
        state_list.append(active_metric_dict['output'].strip().upper())
    state = NODE_ON if NODE_ON in state_list else NODE_OFF
    covert_state = {NODE_ON: 'on', NODE_OFF: 'off'}
    metrics_dict['node_active'] = \
        {'value': covert_state[state], 'unit': '', 'output': ''}


def convert_datasource(datasource_results, hostlist):
    node_info_dict = defaultdict(dict)
    for datasource in datasource_results:
        if not datasource:
            continue
        for points in datasource.get_points():
            host = points['hostname']
            if host not in hostlist:
                continue
            value, metric, output_data, unit = \
                points['value'], points['metric'], \
                points['output'], points['unit']
            value, unit = convert_unit(value, unit)
            value_dict = {
                'value': str(value),
                'unit': unit,
                'output': output_data
            }
            node_info_dict[host][metric] = value_dict

    off_nodes = set(hostlist) - set(node_info_dict.keys())
    if off_nodes:
        for off_node in off_nodes:
            node_info_dict[off_node]['rta'] = \
                {'value': '', 'output': 'DOWN', 'unit': 'seconds'}
            node_info_dict[off_node]['pl'] = \
                {'value': '', 'output': 'DOWN', 'unit': 'percent'}

    """
        node_info_dict for example:
            {
                'head': {
                    'cpu_util': {
                        'value': '10',
                        'output': '[OK] - CPU Utiliztion = 10%',
                        'unit': '%'},
                    ...
                    'rta': {
                        'value': '0.00023',
                        'output': 'UP', # UP or DOWN
                        'unit': 'seconds'
                    },
                    'pl': {
                        'value': '0',
                        'output': 'UP', # UP or DOWN
                        'unit': 'percent'
                   }
                },
                ...
            }
    """
    return node_info_dict


def init_datasource():
    datasource_list = list()
    source_sql = _generator_sql()
    try:
        datasource_results = DataSourceInfluxClient().get(source_sql)
    except Exception as e:
        message = 'Datasource influxdb client get data exception, ' \
                  'Error message: {}'.format(e)
        logger.exception(message)
        return datasource_list
    hostlist = ClusterClient().get_hostlist()
    if not datasource_results:
        return datasource_list
    node_info_dict = convert_datasource(datasource_results, hostlist)

    for hostname, metrics_dict in node_info_dict.items():
        node_info = \
            NodesInfo(hostname, NodeMetric(), GpuPhysicsMetric(), JobMetric())
        _init_datasource(metrics_dict)
        memory_total = metrics_dict.get('memory_total', {}).get('value', 0)
        for metric, value_dict in metrics_dict.items():
            if not value_dict:
                continue
            if metric.startswith('gpu'):
                set_gpu_attr(metric, node_info.gpu_metric, value_dict)
                continue
            if metric.startswith('job'):
                set_job_attr(
                    metric, node_info.job_metric, value_dict, memory_total
                )
                continue
            set_node_attr(metric, node_info.node_metric, value_dict)
        datasource_list.append(node_info)
    return datasource_list


def parse_gpu_logical_info(node_info, gpu_dict, gpu_metric=None):
    for gpu_info in node_info['gpu']:
        index = gpu_info['index']
        vendor = gpu_info['vendor']
        occupy = int(gpu_info['occupation']) \
            if gpu_info['occupation'] in [True, False, 1, 0] else None
        gpu_dict['used'][index] = occupy
        gpu_dict['vendor'][index] = Gpu.VENDOR[vendor][1]
        gpu_dict['product'][index] = gpu_info['type']
        if gpu_metric:
            gpu_dict['value'][index] = gpu_info[gpu_metric]
        gpu_dev_detail = gpu_info['gpu_logical_device']
        if not gpu_dev_detail:
            continue

        gpu_dev_dict = defaultdict(dict)
        """
            {
                '<dev_id>': {
                    'name': 'aaaaa',
                    'used': 1,
                    'util': '',
                    'temperature': '',
                    'memory_usage': ''
                },
                ...
            }
        """
        for dev_dict in gpu_dev_detail:
            metric = dev_dict['metric']
            dev_id = dev_dict['dev_id'].split('.')[0]
            value = dev_dict['value']
            if metric == 'proc_num':
                value = float(value) if value else 0
                gpu_dev_dict[dev_id]['used'] = 1 if value else 0
                continue
            if metric in ['name', 'util', 'temperature', 'memory_usage']:
                gpu_dev_dict[dev_id][metric] = value
            if vendor == Gpu.INTEL:
                gpu_dev_dict[dev_id].update({'name': ''})
                gpu_dev_dict[dev_id].update({'used': occupy})

        gpu_dict['logical_dev_info'][index] = \
            [[] for i in range(len(gpu_dev_dict))]
        for dev_index, dev_tp in enumerate(sorted(gpu_dev_dict.items())):
            dev_id, dev_dict = dev_tp
            gpu_dict['logical_dev_info'][index][dev_index].extend(
                [dev_dict.get('name', None), dev_dict.get('used', None)]
            )
            if vendor == Gpu.INTEL:
                util = dev_dict.get("util", None)
                usage = dev_dict.get("memory_usage", None)
                temp = dev_dict.get("temperature", None)
                gpu_dict['logical_dev_info'][index][dev_index].extend(
                    [util, usage, temp])


def get_allocation_core():
    from lico.core.contrib.client import Client
    resource_data = Client().job_client().get_host_resource_used()
    hostlist = Client().cluster_client().get_hostlist()
    node_alloc_dict = dict()
    for hostname in hostlist:
        allocating_core = \
            resource_data.get(hostname, {}).get('core_total_num', '0')
        node_alloc_dict[hostname] = int(allocating_core)
    """
    ResultSet for example:
    {
        'head': 10,
        'c1': 0
    }
    """
    return node_alloc_dict


class NodeSchedulerProcess:

    def get_node_gpus(self, hostname):
        node = MonitorNode.objects.filter(hostname=hostname)
        gpus = node[0].gpu.all() if node else []
        gpus_used_info = defaultdict(defaultdict)
        for gpu in gpus:
            gpus_used_info[gpu.index]["type"] = gpu.type
            gpus_used_info[gpu.index]["util"] = gpu.util
            for sub_gpu in gpu.gpu_logical_device.filter(
                    Q(metric="sm") | Q(metric="util") | Q(metric="name")
            ):
                dev_info = gpus_used_info[gpu.index].get(sub_gpu.dev_id, {})
                dev_info.update({sub_gpu.metric: sub_gpu.value})
                gpus_used_info[gpu.index][sub_gpu.dev_id] = dev_info
        """
        {
            0: {
                "type": "",
                "util": 123,
                "0.1.0": {
                    "util": None,
                    "sm": None,
                    "name": None,
                }
            },
            ...
        }
        """
        return gpus_used_info

    def convert2list(self, obj):
        if not isinstance(obj, list):
            obj = [obj, ]
        return obj

    def calculate_process_gpu_util(
            self, gpu_index, node_gpus_usage, process_info, pid_on_gpu_info):
        pid = process_info["pid"]

        process_usage = pid_on_gpu_info.get(pid, None)
        if process_usage:
            pid_on_gpu_info[pid]["gpu"].update({
                gpu_index: {
                    "type": node_gpus_usage[gpu_index]["type"],
                    "util": node_gpus_usage[gpu_index]["util"],
                }
            })
            pid_on_gpu_info[pid][
                "util_total"] += node_gpus_usage[gpu_index]["util"]
        else:
            pid_on_gpu_info[pid] = {
                "gpu": {
                    gpu_index: {
                        "type": node_gpus_usage[gpu_index]["type"],
                        "util": node_gpus_usage[gpu_index]["util"],
                    }
                },
                "util_total": node_gpus_usage[gpu_index]["util"]
            }

    def calculate_process_gpu_util_with_mig(
            self, gpu_index, node_gpus_usage, gpu_mig_info, sm_total,
            process_info, pid_on_gpu_info):
        gpu_instance_id = process_info["gpu_instance_id"]
        compute_instance_id = process_info["compute_instance_id"]
        pid = process_info["pid"]
        mig_dev = gpu_mig_info.get(
            gpu_instance_id, {}).get(compute_instance_id, None).get("mig_dev")
        mig_sm = gpu_mig_info.get(
            gpu_instance_id, {}).get(compute_instance_id, None).get("sm")
        gpu_mig_util = round(mig_sm / sm_total, 2) * 100

        process_usage = pid_on_gpu_info.get(pid, None)
        if not process_usage:
            pid_on_gpu_info[pid] = {
                "gpu": {
                    gpu_index: {
                        "type": node_gpus_usage[gpu_index]["type"],
                        "util": gpu_mig_util,
                        "mig_devs": {
                            mig_dev: {
                                "dev_util": "100",
                                "dev_name": node_gpus_usage[
                                    gpu_index
                                ][
                                    f"{mig_dev}.{gpu_instance_id}."
                                    f"{compute_instance_id}"
                                ]["name"]
                            }
                        }
                    }
                },
                "util_total": gpu_mig_util
            }
        else:
            gpu_used = pid_on_gpu_info[pid]["gpu"].get(gpu_index)
            if gpu_used:
                pass
            else:
                pid_on_gpu_info[pid]["gpu"].update({
                    gpu_index: {
                        "type": node_gpus_usage[gpu_index]["type"],
                        "util": gpu_mig_util,
                        "mig_devs": {
                            mig_dev: {
                                "dev_util": "100",
                                "dev_name": node_gpus_usage[
                                    gpu_index
                                ][
                                    f"{mig_dev}.{gpu_instance_id}."
                                    f"{compute_instance_id}"
                                ]["name"]
                            }
                        }
                    }
                })
                pid_on_gpu_info[pid]["util_total"] += gpu_mig_util

    def get_nvidia_gpu_sm_total(self, conn, gpu_index):
        cmd = ["nvidia-smi", "mig", "-lgip", "-i", str(gpu_index)]
        out = conn.run(cmd).stdout
        sm_total = out.splitlines()[-3].split()[-4]
        return int(sm_total)

    def get_nvidia_gpu_process_info(self, hostname, conn):
        node_gpus_usage = self.get_node_gpus(hostname=hostname)

        cmd = ["nvidia-smi", "-q", "-x"]
        out = conn.run(cmd).stdout
        gpu_info = xmltodict.parse(out)

        pid_on_gpu_info = dict()
        gpus = gpu_info.get("nvidia_smi_log", {}).get("gpu", [])
        gpus = self.convert2list(gpus)
        for gpu in gpus:
            if not gpu.get("processes"):
                continue
            gpu_index = int(gpu["minor_number"])
            gpu_mig_info = defaultdict(defaultdict)
            sm_total = 0
            if gpu["mig_mode"]["current_mig"] == "Enabled":
                mig_devices = gpu.get("mig_devices", {}).get("mig_device", [])
                mig_devices = self.convert2list(mig_devices)
                for mig_device in mig_devices:
                    mig_dev = mig_device["index"]
                    gi = mig_device["gpu_instance_id"]
                    ci = mig_device["compute_instance_id"]
                    sm = int(mig_device[
                                 "device_attributes"]["shared"][
                                 "multiprocessor_count"])
                    gpu_mig_info[gi][ci] = {
                        "mig_dev": mig_dev,
                        "sm": sm
                    }
                    sm_total = self.get_nvidia_gpu_sm_total(conn, gpu_index)
            gpu_process_info = gpu.get("processes").get("process_info", [])
            gpu_process_info = self.convert2list(gpu_process_info)
            for process_info in gpu_process_info:
                if gpu["mig_mode"]["current_mig"] == "Enabled":
                    self.calculate_process_gpu_util_with_mig(
                        gpu_index, node_gpus_usage, gpu_mig_info, sm_total,
                        process_info, pid_on_gpu_info)
                else:
                    self.calculate_process_gpu_util(
                        gpu_index, node_gpus_usage, process_info,
                        pid_on_gpu_info)
        return pid_on_gpu_info

    def get_intel_xpu_process_info(self, hostname, conn):
        """
        {
            "device_util_by_proc_list": [
                {
                    "device_id": 0,
                    "mem_size": 5726404,
                    "process_id": 768707,
                    "process_name": "python",
                    "shared_mem_size": 0
                },
                {
                    "device_id": 0,
                    "mem_size": 1507,
                    "process_id": 5225,
                    "process_name": "slurmd",
                    "shared_mem_size": 0
                },
                {
                    "device_id": 0,
                    "mem_size": 17238523,
                    "process_id": 4615,
                    "process_name": "xpumd",
                    "shared_mem_size": 0
                }
            ]
        }
        """
        cmd = "xpumcli ps -j"
        out = conn.run(cmd.split()).stdout
        out = json.loads(out)

        node_gpus_usage = self.get_node_gpus(hostname=hostname)

        pid_on_gpu_info = dict()
        for process_info in out.get("device_util_by_proc_list", []):
            xpu_index = process_info.get("device_id")
            pid = str(process_info.get("process_id"))

            process_usage = pid_on_gpu_info.get(pid)
            if process_usage:
                pid_on_gpu_info[pid]["gpu"].update({
                    xpu_index: {
                        "type": node_gpus_usage[xpu_index]["type"],
                        "util": node_gpus_usage[xpu_index]["util"],
                    }
                })
                pid_on_gpu_info[pid][
                    "util_total"] += node_gpus_usage[xpu_index]["util"]
            else:
                pid_on_gpu_info[pid] = {
                    "gpu": {
                        xpu_index: {
                            "type": node_gpus_usage[xpu_index]["type"],
                            "util": node_gpus_usage[xpu_index]["util"],
                        }
                    },
                    "util_total": node_gpus_usage[xpu_index]["util"]
                }

        return pid_on_gpu_info

    def is_exclude_process(self, process_cmd):
        exclude_process = {"slurmd", "xpumd"}
        process_cmd = os.path.basename(process_cmd)
        return process_cmd in exclude_process

    def get_process_info(
            self, conn, pid_job_info, gpu_process_info, scheduler_id, pids):

        title = ['pid', 'user', 'cpu_util', 'mem_util', 'runtime', 'cmd']
        # cmd = ["ps", "-eo", "user,pid,%cpu,%mem,time,args:512"]
        cmd = ["top", "-b", "-n", "1", "-c", "-w", "512"]
        out = conn.run(cmd).stdout
        data = out.splitlines()
        # PID USER   PR  NI    VIRT    RES    SHR S  %CPU  %MEM  TIME+ COMMAND
        cmd_title = data[6].split()
        pid_details = dict()
        for item in data[7:]:
            info = item.split()
            pid_info = dict(zip(cmd_title[:-1], info[:len(cmd_title)]))
            if pids and pid_info["PID"] not in pids:
                continue
            if scheduler_id and pid_info["PID"] not in pid_job_info:
                continue
            pid_info[cmd_title[-1]] = " ".join(
                info[cmd_title.index("COMMAND"):])
            process_cmd = info[cmd_title.index("COMMAND")]
            if self.is_exclude_process(process_cmd):
                logger.info(f"Hidden process: {process_cmd}")
                continue
            pid_details[pid_info["PID"]] = dict(zip(title, [
                pid_info["PID"],
                pid_info["USER"],
                pid_info["%CPU"],
                pid_info["%MEM"],
                pid_info["TIME+"],
                pid_info["COMMAND"],
            ]))
            pid_details[pid_info["PID"]].update(
                pid_job_info.get(pid_info["PID"], {}))

            """
            {
                "gpu": {
                    0: {
                        # "mig_devs": {
                        #     0: {
                        #         "dev_name": "3g.20gb",
                        #         "dev_util": "100"
                        #     }
                        # },
                        "type": "NVIDIA A100-PCIE-40GB",
                        "util": 40
                    },
                    ......
                },
                "util_total": 40
            }
            """
            if gpu_process_info:
                pid_gpu_usage = gpu_process_info.get(pid_info["PID"])
                pid_details[pid_info["PID"]]["gpu_util"] = pid_gpu_usage

        return pid_details

    def get_process_job_info(self, hostname, conn, scheduler_id):
        """
        {
            pid: {
                "job_name": "",
                "scheduler_id": 21
            }
        }
        """
        scheduler = get_admin_scheduler()
        # scheduler_id: [pid, ...]
        funs = scheduler.get_parse_job_pidlist_funs()
        result = []
        for i in range(0, len(funs), 2):
            ret = funs[i](result)
            cmd_out = conn.run(ret).stdout
            ret = funs[i + 1](cmd_out, hostname, result)
            result.append(ret)
        job_pids = result[-1]

        running_jobs = Client().job_client().query_running_jobs()
        pid_job_info = dict()
        for r_job in running_jobs:
            for pid in job_pids.get(r_job.scheduler_id, []):
                if scheduler_id and r_job.scheduler_id != scheduler_id:
                    continue
                pid_job_info[pid] = {
                    "job_id": r_job.id,
                    "job_name": r_job.job_name,
                    "scheduler_id": r_job.scheduler_id
                }
        return pid_job_info
