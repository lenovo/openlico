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

from ..scanner.checker import AlertCheck


def cpu_scanner():
    AlertCheck.checker("cpu")


def memory_scanner():
    AlertCheck.checker("memory_util")


def disk_scanner():
    AlertCheck.checker("disk")


def energy_scanner():
    AlertCheck.checker("energy")


def temp_scanner():
    AlertCheck.checker("temperature")


def hardware_scanner():
    AlertCheck.checker("hardware")


def node_active():
    AlertCheck.checker("node_active")


def gpu_util_scanner():
    AlertCheck.checker("gpu_util")


def gpu_temp_scanner():
    AlertCheck.checker("gpu_temperature")


def gpu_mem_scanner():
    AlertCheck.checker("gpu_memory")


def hardware_dis_scanner():
    AlertCheck.checker("hardware_discovery")
