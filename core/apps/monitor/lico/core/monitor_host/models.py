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

from typing import Callable, Dict

from django.db.models import (
    CASCADE, BigIntegerField, BooleanField, CharField, FloatField, ForeignKey,
    IntegerField, TextField,
)

from lico.core.contrib.fields import DateTimeField, JSONField
from lico.core.contrib.models import Model


class MonitorNode(Model):
    # HYPERVISOR_MODE = [
    #     (0, "physical machine"),
    #     (1, "virtual machine")
    # ]
    PHYSICAL_MACHINE = 0
    VIRTUAL_MACHINE = 1

    hostname = CharField(
        primary_key=True, null=False,
        unique=True, max_length=254
    )

    node_active = BooleanField(
        null=False,
        default=False,
        help_text="True: power on; False: power off"
    )  # power_status
    cpu_util = FloatField(null=True, help_text="Unit: %")
    cpu_load = FloatField(null=True)
    cpu_socket_num = IntegerField(default=0)
    cpu_thread_per_core = IntegerField(default=0)
    cpu_core_per_socket = IntegerField(default=0)
    hypervisor_vendor = CharField(max_length=100, null=True, default=None)

    disk_total = FloatField(default=0, help_text=b'unit:GiB')
    disk_used = FloatField(null=True, help_text=b'unit:GiB')
    memory_total = FloatField(default=0, help_text=b'unit:KiB')
    memory_used = FloatField(null=True, help_text=b'unit:KiB')
    eth_in = FloatField(null=True, help_text=b'unit:MiB/s')
    eth_out = FloatField(null=True, help_text=b'unit:MiB/s')
    ib_in = FloatField(null=True, help_text=b'unit:MiB/s')
    ib_out = FloatField(null=True, help_text=b'unit:MiB/s')

    health = CharField(max_length=100, default='unknown')
    temperature = FloatField(null=True, help_text="Unit: C")
    power = FloatField(null=True)

    create_time = DateTimeField(auto_now_add=True)
    update_time = DateTimeField(auto_now=True)

    @property
    def hypervisor_mode(self):
        return self.VIRTUAL_MACHINE if self.hypervisor_vendor \
            else self.PHYSICAL_MACHINE

    @property
    def cpu_total(self):
        return self.cpu_thread_per_core * self.cpu_core_per_socket \
               * self.cpu_socket_num

    @property
    def disk_util(self):
        if self.disk_used is not None and self.disk_total:
            return round((self.disk_used / self.disk_total) * 100.0, 2)

    @property
    def memory_util(self):
        if self.memory_used is not None and self.memory_total:
            return round((self.memory_used / self.memory_total) * 100.0, 2)

    def as_dict_on_finished(self, result: Dict, is_exlucded: Callable,
                            **kwargs):
        if not is_exlucded("cpu_total"):
            result["cpu_total"] = self.cpu_total
        if not is_exlucded("disk_util"):
            result["disk_util"] = self.disk_util
        if not is_exlucded("memory_util"):
            result["memory_util"] = self.memory_util


class HardwareHealth(Model):
    monitor_node = ForeignKey(
        "MonitorNode", related_name="hardware_health",
        null=False, on_delete=CASCADE
    )
    health = CharField(null=False, max_length=100)
    name = CharField(null=False, max_length=100)
    states = TextField(null=False, blank=True, default='')
    units = CharField(null=True, max_length=100)
    value = CharField(null=True, default='', max_length=100)
    type = CharField(max_length=100)
    create_time = DateTimeField(auto_now_add=True)


class Gpu(Model):
    NVIDIA = 0
    INTEL = 1
    AMD = 2
    VENDOR = [
        (NVIDIA, "NVIDIA"),
        (INTEL, "INTEL"),
        (AMD, "AMD")
    ]

    index = IntegerField(null=False)
    type = CharField(null=False, max_length=100, default="")
    vendor = IntegerField(choices=VENDOR, null=True)
    driver_version = CharField(null=False, max_length=100, default="")
    uuid = CharField(max_length=128, null=True)
    parent_uuid = CharField(max_length=128, null=True)
    occupation = BooleanField(null=True, default=False,
                              help_text="True: used; False: free")
    memory_used = IntegerField(null=True, help_text="Unit: KiB")
    memory_total = IntegerField(default=0, help_text="Unit: KiB")
    util = IntegerField(null=True, help_text="Unit: %")
    temperature = IntegerField(null=True, help_text="Unit: C")

    mig_mode = BooleanField(default=False)
    pcie_generation = JSONField(default=dict)
    bandwidth_util = IntegerField(null=True, help_text="Unit: %")
    monitor_node = ForeignKey(
        'MonitorNode', related_name="gpu", null=False, on_delete=CASCADE
    )

    @property
    def pcie_max(self):
        return self.pcie_generation.get('max', '')

    @property
    def pcie_current(self):
        return self.pcie_generation.get('current', '')

    @property
    def memory_util(self):
        if self.memory_used is not None and self.memory_total:
            return round((self.memory_used / self.memory_total) * 100.0, 2)

    def as_dict_on_finished(self, result: Dict, is_exlucded: Callable,
                            **kwargs):
        if not is_exlucded("memory_util"):
            result["memory_util"] = self.memory_util
        if not is_exlucded("pcie_max"):
            result["pcie_max"] = self.pcie_max
        if not is_exlucded("pcie_current"):
            result["pcie_current"] = self.pcie_current

    class Meta:
        unique_together = ('index', 'monitor_node')


class GpuLogicalDevice(Model):
    gpu = ForeignKey(
        'Gpu', related_name='gpu_logical_device', null=False, on_delete=CASCADE
    )
    dev_id = CharField(max_length=100)
    metric = CharField(null=False, max_length=100)
    value = TextField(null=False, default='')
    units = CharField(null=True, max_length=100)
    create_time = DateTimeField(auto_now_add=True)
    update_time = DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('gpu', 'dev_id', 'metric')


class Cluster(Model):
    name = CharField(null=False, max_length=100)
    metric = CharField(null=False, max_length=100)
    value = TextField(null=True)
    create_time = DateTimeField(auto_now_add=True)
    update_time = DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('name', 'metric')


class VNC(Model):
    monitor_node = ForeignKey(
        "MonitorNode", related_name="vnc",
        null=False, on_delete=CASCADE
    )
    index = CharField(null=False, max_length=100)
    detail = JSONField(null=True)
    create_time = DateTimeField(auto_now_add=True)
    update_time = DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('monitor_node', 'index')


class Preference(Model):
    name = CharField(max_length=256)
    value = TextField(null=False)
    username = CharField(
        max_length=32,
        null=True,
        help_text=b'null:scope is global, otherwise scope is local'
    )
    create_time = DateTimeField(auto_now_add=True)
    modify_time = DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('name', 'username')


class NodeSchedulableRes(Model):
    hostname = CharField(null=False, unique=True, max_length=254)
    state = CharField(null=True, max_length=254)
    cpu_total = IntegerField(null=True)
    cpu_util = FloatField(null=True, help_text="Unit: %")
    mem_total = BigIntegerField(null=True, help_text="Unit: KB")
    mem_used = FloatField(null=True, help_text="Unit: KB")
    gres = TextField(null=False, default='{}')
    create_time = DateTimeField(auto_now_add=True)
    update_time = DateTimeField(auto_now=True)
