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
import os.path
from collections import defaultdict

import xmltodict
from django.db.models import Count, Max, Min, Q
from rest_framework import status
from rest_framework.response import Response

from lico.core.contrib.authentication import (
    JWTInternalAnonymousAuthentication, RemoteJWTWebAuthentication,
)
from lico.core.contrib.client import Client
from lico.core.contrib.permissions import AsUserRole
from lico.core.contrib.schema import json_schema_validate
from lico.core.contrib.views import APIView, DataTableView, InternalAPIView
from lico.core.monitor_host.exceptions import (
    HostNameDoesNotExistException, SSHConnectException,
)
from lico.core.monitor_host.utils import parse_gpu_logical_info
from lico.ssh.ssh_connect import RemoteSSH

from ..models import Gpu, MonitorNode
from ..utils import (
    BUSY_THRESHOLD, IDLE_THRESHOLD, ResourceFactory, get_admin_scheduler,
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
                        "device_attributes"]["shared"]["multiprocessor_count"])
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

    def get(self, request, hostname):
        scheduler_id = request.query_params.get("scheduler_id", None)
        pids = json.loads(request.query_params.get("pids", "[]"))

        conn = RemoteSSH(hostname)
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
                    gpu_process_info = self.get_nvidia_gpu_process_info(
                        hostname, conn)
                elif gpu.vendor == Gpu.INTEL:
                    gpu_process_info = self.get_intel_xpu_process_info(
                        hostname, conn)
            except Exception as e:
                logger.warning(e)
            try:
                pid_job_info = self.get_process_job_info(
                    hostname, conn, scheduler_id)
            except Exception as e:
                logger.warning(e)
                pid_job_info = {}
            pids = self.get_process_info(
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
