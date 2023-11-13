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
from typing import Any, Callable, Union

import attr
from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.db.utils import IntegrityError
from psutil import disk_usage

from lico.core.monitor_host.models import Cluster, Gpu, MonitorNode
from lico.core.monitor_host.utils import (
    ClusterClient, convert_unit, init_datasource,
)

logger = logging.getLogger(__name__)

# {metric name in db: field name in NodeMetric}
node_map = {
    "node_active": "node_active",
    "cpu_socket_num": "cpu_socket_num",
    "cpu_core_per_socket": "cpu_core_per_socket",
    "cpu_thread_per_core": "cpu_thread_per_core",
    "disk_total": "disk_total",
    "memory_total": "memory_total",
    "hypervisor_vendor": "hypervisor_mode",
    "health": "node_health",
    "cpu_util": "cpu_util",
    "cpu_load": "cpu_load",
    "disk_used": "disk_used",
    "memory_used": "memory_used",
    "eth_in": "eth_in",
    "eth_out": "eth_out",
    "ib_in": "ib_in",
    "ib_out": "ib_out",
    "temperature": "node_temp",
    "power": "node_power"
}
# {field name in GpuPhysicsMetric: needed metric name}
gpu_map = {
    "gpu_util": "util",
    "gpu_temp": "temperature",
    "gpu_mem_used": "memory_used",
    "gpu_mem_total": "memory_total",
    "gpu_util_mem": "bandwidth_util",
    "gpu_proc_num": "occupation",
    "gpu_product_name": "type",  # vendor in output
    "gpu_uuid": "uuid",  # vendor in output
    "gpu_driver": "driver_version",
    "gpu_pcie_generation": "pcie_generation",
    "gpu_mig_mode": "mig_mode",
    "gpu_dev_model": "gpu_device",
    # "gpu_dev_spec": "mig_name",
}
# {static metric name in db: metric name in output}
gpu_static = {
    "type": "product_name",
    "driver_version": "driver_version",
    "uuid": "uuid",
    "pcie_generation": "pcie_generation",
}
# {field name in GpuLogicMetric which gpu vendor is nvidia
# : needed metric name}
# mig_metric_map = {
#     "gpu_dev_spec": "name",
#     "gpu_dev_mem_used": "memory_used",
#     "gpu_dev_proc_num": "proc_num",
#     "gpu_dev_mem_total": "memory_total",
#     "gpu_dev_sm_count": "sm"
# }
# tile_metric_map = {
#     "gpu_dev_mem_used": "memory_used",
#     "gpu_dev_temp": "temperature",
#     "gpu_dev_util": "util",
#     "gpu_dev_util_bandwidth": "bandwidth_util",
#     "gpu_dev_mem_usage": "memory_usage"
# }
gpu_logic_metric_map = {
    "gpu_dev_mem_used": "memory_used",

    "gpu_dev_spec": "name",
    "gpu_dev_proc_num": "proc_num",
    "gpu_dev_mem_total": "memory_total",
    "gpu_dev_sm_count": "sm",

    "gpu_dev_temp": "temperature",
    "gpu_dev_util": "util",
    "gpu_dev_util_bandwidth": "bandwidth_util",
    "gpu_dev_mem_usage": "memory_usage"
}

type_mapping = {
    "cpu_util": float,
    "cpu_load": float,
    "cpu_socket_num": float,
    "cpu_thread_per_core": float,
    "cpu_core_per_socket": float,
    "disk_total": lambda x: round(convert_unit(
        x, "BYTES", "GiB")[0], 2),
    "disk_used": lambda x: round(convert_unit(
        x, "BYTES", "GiB")[0], 2),
    "memory_total": lambda x: round(convert_unit(
        x, "BYTES", "KiB")[0], 2),
    "memory_used": lambda x: round(convert_unit(
        x, "BYTES", "KiB")[0], 2),
    "eth_in": lambda x: round(convert_unit(
        x, "BYTES", "MiB")[0], 2),
    "eth_out": lambda x: round(convert_unit(
        x, "BYTES", "MiB")[0], 2),
    "ib_in": lambda x: round(convert_unit(
        x, "BYTES", "MiB")[0], 2),
    "ib_out": lambda x: round(convert_unit(
        x, "BYTES", "MiB")[0], 2),
    "node_active": lambda x: True if x.lower() == "on" else False,
    # "hypervisor_vendor": str,
    "temperature": float,
    "power": float,
}
gpu_type_mapping = {
    "vendor": lambda x: int(float(x)),
    "memory_used": lambda x: round(convert_unit(
        x, "BYTES", "KIB")[0], 2),
    "memory_total": lambda x: round(convert_unit(
        x, "BYTES", "KIB")[0], 2),
    "util": float,
    "temperature": float,
    "bandwidth_util": float,
    "mig_mode": float
}


class LatestMonitorSync:

    def __init__(self, data_list=None):
        self.monitor_data = data_list if data_list else init_datasource()
        self.cluster = defaultdict(dict)
        self.format_value: Callable[[Any], Union[int, Any]] = \
            lambda x: x if x is not None and x > 0 else 0

        self.cluster_metric = {
            "cpu_count": 0, "cpu_util": 0, "disk_total": 0, "disk_used": 0,
            "memory_total": 0, "memory_used": 0, "eth_in": 0, "eth_out": 0,
            "ib_in": 0, "ib_out": 0, "temperature": None, "power": 0,
            "gpu_card_total": 0, "gpu_card_used": 0, "gpu_dev_total": 0,
            "gpu_dev_used": 0, "gpu_allocable_total": 0,
            "gpu_allocable_used": 0, "gpu_memory_total": 0,
            "gpu_memory_used": 0, "gpu_util": 0
        }
        self.node_default_dict = {
            "cpu_util": None, "cpu_load": None, "disk_used": None,
            "memory_used": None, "eth_in": None, "eth_out": None,
            "ib_in": None, "ib_out": None, "health": "unknown",
            "temperature": None, "power": None,
            "node_active": False}
        self.gpu_default_dict = {
            "occupation": False, "util": None,
            "memory_used": None, "temperature": None,
        }
        self.gpu_logic_default_list = [
            "memory_used", "proc_num", "util",
            "temperature", "bandwidth_util", "memory_usage"
        ]

    def update(self):
        hostlist = ClusterClient().get_hostlist()
        MonitorNode.objects.exclude(
            hostname__in=hostlist
        ).delete()

        self.update_no_monitor()

        for nodes_info in self.monitor_data:
            if self._node_status(nodes_info.hostname,
                                 attr.asdict(nodes_info.node_metric)):
                try:
                    self.save_node(nodes_info.hostname,
                                   attr.asdict(nodes_info.node_metric))
                    self.save_gpu(nodes_info.hostname,
                                  attr.asdict(nodes_info.gpu_metric))
                except IntegrityError as e:
                    self._modify_cluster_metric(nodes_info.hostname)
                    logger.info(e)
                    continue
                except Exception as e:
                    logger.info(e)
                    continue
            else:
                continue

        self.save_cluster()

    def _node_status(self, hostname, node_dict):
        node_status = type_mapping["node_active"](node_dict.get(
            "node_active", {}).get("value", ""))

        has_monitor = False
        if node_status:  # on
            node_dict.pop('node_active')
            for metric, value in node_dict.items():
                # node_active is on and monitor_data has data
                if value:
                    has_monitor = True
                    return has_monitor

        self.node_default_dict['node_active'] = node_status
        # node_active is off or node_active is on but don't have monitor_data
        node, _ = MonitorNode.objects.update_or_create(
            hostname=hostname, defaults=self.node_default_dict)
        self._no_monitor_gpu(node)

        # add for node don't have monitor data
        if not has_monitor and node_status:
            self._extra_cluster_metric(node)

    def _modify_cluster_metric(self, hostname):
        try:
            self.cluster.pop(hostname)
            node = MonitorNode.objects.get(hostname=hostname)
            self._extra_cluster_metric(node)
        except Exception as e:
            logger.info(e)

    def _extra_cluster_metric(self, node):
        self.cluster_metric["cpu_count"] += self.format_value(
            node.cpu_total)
        self.cluster_metric["memory_total"] += \
            self.format_value(node.memory_total)

        self.cluster_metric["gpu_card_total"] += node.gpu.count()

        gpu_allocable_total, gpu_dev_total, logic_num = 0, 0, 0
        for gpu in node.gpu.all():
            if gpu.vendor == Gpu.NVIDIA:
                if gpu.mig_mode == 1:
                    logic_num = gpu.gpu_logical_device.values(
                        'dev_id').distinct().count()
            elif gpu.vendor == Gpu.INTEL:
                logic_num = gpu.gpu_logical_device.values(
                    'dev_id').distinct().count()
            gpu_allocable_total += logic_num if logic_num > 0 else 1
            gpu_dev_total += logic_num
        self.cluster_metric["gpu_allocable_total"] += gpu_allocable_total
        self.cluster_metric["gpu_dev_total"] += gpu_dev_total

        self.cluster_metric["gpu_memory_total"] += self.format_value(
            node.gpu.aggregate(Sum("memory_total")).get(
                "memory_total__sum"))

    def _no_monitor_gpu(self, node):
        # update gpu dynamic data for host is shut down or monitor
        # service is stopped
        node.gpu.update(**self.gpu_default_dict)

        for gpu in node.gpu.all():
            gpu.gpu_logical_device.filter(
                metric__in=self.gpu_logic_default_list).update(value='')

    def update_no_monitor(self):
        # update dynamic data for nodes that not in the return
        # of init_datasource but in cluster_client.get_hostlist()
        monitor_host_list = [
            nodes_info.hostname for nodes_info in self.monitor_data]
        nodes = MonitorNode.objects.exclude(hostname__in=monitor_host_list)
        if nodes:
            nodes.update(**self.node_default_dict)
            for node in nodes:
                self._no_monitor_gpu(node)

    @staticmethod
    def _delete_status(output):
        try:
            out = re.sub(r"\[\w+\] - ", "", literal_eval(
                "'{}'".format(output)))
            return json.loads(out)
        except Exception:
            return

    def parse_node(self, node_metric):
        node_dict = {}

        for db_field, node_field in node_map.items():
            try:
                if db_field == "health":
                    node_dict[db_field] = self._delete_status(
                        node_metric.get(node_field).get("output")
                    )
                elif db_field == "hypervisor_vendor":
                    if int(float(node_metric.get(node_field).get(
                            "value"))) == MonitorNode.VIRTUAL_MACHINE:
                        vendor = node_metric.get(node_field).get(
                            "output").split(",")[-1].split("=")[-1].strip()
                        node_dict[db_field] = vendor
                    else:
                        node_dict[db_field] = ""
                else:
                    value = node_metric.get(node_field).get("value")
                    node_dict[db_field] = type_mapping[db_field](value) \
                        if value is not None else None

            except Exception as e:
                logger.info(e)
                continue

        return node_dict

    @transaction.atomic
    def save_node(self, hostname, node_metric):
        node_dict = self.parse_node(node_metric)
        self.cluster[hostname]["node"] = node_dict

        try:
            health = node_dict.pop("health")
            node_dict["health"] = health.get("health", "unknown")
        except Exception as e:
            logger.info(e)
            health = {}

        node, _ = MonitorNode.objects.update_or_create(
            hostname=hostname,
            defaults=node_dict
        )

        update_names = []
        for sensor in health.get("badreadings", []):
            # ipmi
            if sensor.get("name"):
                hardware_health, _ = node.hardware_health.update_or_create(
                    name=sensor.get("name"),
                    defaults={
                        'health': sensor.get('health', ''),
                        'states': sensor.get('states', ''),
                        'units': sensor.get('units', ''),
                        'value': sensor.get('value', ''),
                        'type': sensor.get('type', '')
                    }
                )
            # redfish
            elif sensor.get("SensorName"):
                hardware_health, _ = node.hardware_health.update_or_create(
                    name=sensor.get("SensorName"),
                    defaults={
                        'health': sensor.get('Severity', ''),
                        'states': sensor.get('Message', ''),
                        'units': sensor.get('units', ''),
                        'value': sensor.get('value', ''),
                        'type': sensor.get('type', '')
                    }
                )
            update_names.append(hardware_health.name)
        node.hardware_health.exclude(name__in=update_names).delete()

    def parse_gpu(self, gpu_physics_metric):
        gpu_dict = defaultdict(dict)
        gpu_logic_dict = defaultdict(dict)

        gpu_logic = self._parse_gpu_physics(gpu_physics_metric, gpu_dict)
        self._parse_gpu_logic_device(gpu_logic, gpu_logic_dict)

        return gpu_dict, gpu_logic_dict

    def _parse_gpu_physics(self, gpu_physics_metric, gpu_dict):
        for field_name, field_value in gpu_physics_metric.items():
            db_field_name = gpu_map.get(field_name)

            if db_field_name == "gpu_device":
                gpu_logic = field_value
                continue

            for index, metrics in field_value.items():
                for info in metrics:
                    try:
                        self._parse_gpu_physics_metric(
                            index, db_field_name, info, gpu_dict)
                    except Exception as e:
                        logger.exception(e)
                        continue

        return gpu_logic

    def _parse_gpu_logic_device(self, gpu_logic, gpu_logic_dict):
        for field_name, logics in gpu_logic.items():
            metric = gpu_logic_metric_map.get(field_name)
            for index, logic_data in logics.items():
                for logic in logic_data:
                    try:
                        self._parse_gpu_logic_metric(
                            index, logic, metric, gpu_logic_dict)
                    except Exception as e:
                        logger.exception(e)
                        continue

    def _parse_gpu_physics_metric(self, index, db_field_name, info, gpu_dict):
        if db_field_name in gpu_static.keys():
            static_data = self._delete_status(
                info.get("output"))
            output = static_data.get(
                index).get(gpu_static.get(db_field_name))
            gpu_dict[index].update({db_field_name: output})
            if db_field_name == "type":
                gpu_dict[index].update({
                    "vendor": gpu_type_mapping["vendor"]
                    (info.get("value"))})
        elif db_field_name == "occupation":
            if float(info.get("value")) > 0:
                gpu_dict[index].update({db_field_name: True})
            else:
                gpu_dict[index].update({db_field_name: False})
        else:
            value = info.get('value')
            gpu_dict[index].update({
                db_field_name: gpu_type_mapping[db_field_name](value)
                if value else value})

    def _parse_gpu_logic_metric(self, index, logic, metric, gpu_logic_dict):
        dev_id = logic.get("dev_id")
        dev = gpu_logic_dict[index].get(dev_id)
        if not dev:
            dev = defaultdict(dict)
            gpu_logic_dict[index].update({dev_id: dev})
        if metric:
            if metric == "name":
                name_output = self._delete_status(
                    logic.get("output")).get(index, {}).get(
                    "logical_device", [])
                for name in name_output:
                    dev_id_in = ".".join(
                        [name.get("dev"),
                         name.get("gi"),
                         name.get("ci")])
                    if dev_id_in == dev_id:
                        dev.update({
                            "name": (name.get("profile"), None)})
                        break
            else:
                dev.update({metric: (logic.get("value"),
                                     logic.get("unit"))})

    @transaction.atomic
    def save_gpu(self, hostname, gpu_physics_metric):
        node, _ = MonitorNode.objects.get_or_create(hostname=hostname)

        gpu_info, gpu_logic_info = self.parse_gpu(gpu_physics_metric)
        self.cluster[hostname]["gpu"] = gpu_info
        self.cluster[hostname]["gpu_logic"] = gpu_logic_info

        update_ids = []
        for index, value in gpu_info.items():
            gpu, _ = node.gpu.update_or_create(
                index=index,
                defaults=value
            )

            devs = gpu_logic_info.get(index, {})
            self.save_gpu_logic_device(gpu, devs)

            update_ids.append(gpu.id)

        node.gpu.exclude(id__in=update_ids).delete()

    @staticmethod
    def save_gpu_logic_device(gpu, devs):
        update_ids = set()

        for dev_id, info in devs.items():
            for metric, value in info.items():
                gpu_dev, _ = gpu.gpu_logical_device.update_or_create(
                    dev_id=dev_id,
                    metric=metric,
                    defaults={"value": value[0], "units": value[1]}
                )
                update_ids.add(gpu_dev.dev_id)

        gpu.gpu_logical_device.exclude(dev_id__in=update_ids).delete()

    def cluster_summary(self):
        cpu_util_sum, cpu_count, node_temp = 0, 0, 0
        host_num = len(self.cluster.keys())

        for host in self.cluster.keys():
            node = self.cluster[host].get("node", {})
            cpu_count = int(
                self.format_value(node.get("cpu_thread_per_core")) *
                self.format_value(node.get("cpu_core_per_socket")) *
                self.format_value(node.get("cpu_socket_num")))
            cpu_util_sum += self.format_value(node.get("cpu_util")) * cpu_count
            self.cluster_metric["cpu_count"] += cpu_count
            self.cluster_metric["memory_total"] += self.format_value(
                node.get("memory_total"))
            self.cluster_metric["memory_used"] += self.format_value(
                node.get("memory_used"))
            self.cluster_metric["eth_in"] += self.format_value(
                node.get("eth_in"))
            self.cluster_metric["eth_out"] += self.format_value(
                node.get("eth_out"))
            self.cluster_metric["ib_in"] += self.format_value(
                node.get("ib_in"))
            self.cluster_metric["ib_out"] += self.format_value(
                node.get("ib_out"))
            self.cluster_metric["power"] += self.format_value(
                node.get("power"))
            if node.get("temperature"):
                node_temp += self.format_value(node.get("temperature"))

            gpus = self.cluster[host].get("gpu", {})
            logic_gpus = self.cluster[host].get("gpu_logic", {})

            self._cluster_gpu_summary(gpus, logic_gpus)

        self.cluster_metric['disk_total'], self.cluster_metric['disk_used'] \
            = self._disk_summaries()

        if self.cluster_metric["cpu_count"] > 0:
            self.cluster_metric["cpu_util"] = \
                cpu_util_sum / self.cluster_metric["cpu_count"]
        if host_num:
            if node_temp:
                self.cluster_metric["temperature"] = node_temp / host_num
        if self.cluster_metric["gpu_card_total"]:
            self.cluster_metric["gpu_util"] = \
                self.cluster_metric["gpu_util"] / self.cluster_metric[
                    "gpu_card_total"]

    @staticmethod
    def _disk_summaries():
        try:
            usage = disk_usage(settings.LICO.SHARE_DIR)
            dfs_total, dfs_used = (
                usage.total / 1024 / 1024 / 1024,
                usage.used / 1024 / 1024 / 1024
            )
            return float(dfs_total), float(dfs_used)
        except OSError:
            return None, None

    def _cluster_gpu_summary(self, gpus, logic_gpus):
        self.cluster_metric["gpu_card_total"] += len(gpus)

        for gpu_index, gpu_data in gpus.items():
            vendor = gpu_data.get("vendor")
            occupation = gpu_data.get("occupation")
            logic_num = len(logic_gpus.get(gpu_index, {}))

            if occupation:
                self.cluster_metric["gpu_card_used"] += 1

            if vendor == Gpu.INTEL:
                self._cluster_intel_summary(gpu_data, logic_num)
            elif vendor == Gpu.NVIDIA:
                self._cluster_nvidia_summary(
                    logic_gpus, logic_num, gpu_index, gpu_data)

            self.cluster_metric["gpu_memory_total"] += self.format_value(
                gpu_data.get("memory_total"))
            self.cluster_metric["gpu_memory_used"] += self.format_value(
                gpu_data.get("memory_used"))
            self.cluster_metric["gpu_util"] += self.format_value(
                gpu_data.get("util"))

    def _cluster_intel_summary(self, gpu_data, logic_num):
        occupation = gpu_data.get("occupation")

        self.cluster_metric["gpu_dev_total"] += logic_num
        self.cluster_metric["gpu_allocable_total"] += logic_num
        if occupation:
            self.cluster_metric["gpu_dev_used"] += logic_num
            self.cluster_metric["gpu_allocable_used"] += logic_num

    def _cluster_nvidia_summary(
            self, logic_gpus, logic_num, gpu_index, gpu_data):
        mig_mode = gpu_data.get("mig_mode")

        if logic_gpus:
            self.cluster_metric["gpu_dev_total"] += logic_num
            for dev_id, logic_data in logic_gpus.get(
                    gpu_index, {}).items():
                if float(logic_data.get("proc_num", (-1, None))[0]) > 0:
                    self.cluster_metric["gpu_dev_used"] += 1
                    if mig_mode:
                        self.cluster_metric["gpu_allocable_used"] += 1
        if mig_mode:
            self.cluster_metric["gpu_allocable_total"] += logic_num
        else:
            self.cluster_metric["gpu_allocable_total"] += 1

    @transaction.atomic
    def save_cluster(self):
        self.cluster_summary()

        update_metrics = []
        for metric, metric_value in self.cluster_metric.items():
            if metric == "temperature" and metric_value is None:
                value = metric_value
            else:
                value = round(metric_value, 2)
            Cluster.objects.update_or_create(
                name=settings.LICO.DOMAIN,
                metric=metric,
                defaults={"value": value}
            )
            update_metrics.append(metric)
        Cluster.objects.exclude(name=settings.LICO.DOMAIN,
                                metric__in=update_metrics).delete()


def sync_latest(data_list):
    LatestMonitorSync(data_list).update()


def sync_vgpu_parent_uuid():
    from lico.core.monitor_host.models import Gpu
    from lico.core.vgpu.models import vGPUNode
    from lico.core.vgpu.utils.common import EncryptData
    from lico.core.vgpu.utils.gpu_device import GpuDeviceManager
    from lico.ssh import RemoteSSH

    vgpu_gpu_dict = dict()
    for node in vGPUNode.objects.all():
        conn = RemoteSSH(
            node.address,
            username=node.username,
            password=EncryptData(
                node.hostname, node.address).decrypt(node.password)
        )
        gpu_info = GpuDeviceManager(conn).get_gpu_info_dict()
        for gpu in gpu_info['gpus']:
            uuid = gpu['uuid']
            for created in gpu['vgpus'].get('created'):
                if bool(created['vm']):
                    vgpu_uuid = created['vgpu_uuid']
                    vgpu_gpu_dict[vgpu_uuid] = uuid

    for vgpu_uuid, uuid in vgpu_gpu_dict.items():
        vgpu = Gpu.objects.filter(uuid=f'GPU-{vgpu_uuid}')
        if vgpu:
            vgpu = vgpu[0]
            vgpu.parent_uuid = uuid
            vgpu.save()
