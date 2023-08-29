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
from typing import Optional

import numpy

from .csres_allocator import CSResAllocator

logger = logging.getLogger(__name__)


class PortAllocator(CSResAllocator):
    def __init__(self, begin_port, end_port):
        self._begin_port = begin_port
        self._end_port = end_port

    def get_csres_code(self) -> str:
        return 'port'

    def next_csres_value(self, allocated_csres_values: list) -> Optional[str]:

        all_ports = range(
            self._begin_port, self._end_port + 1
        )
        allocated_ports = [
            int(csres_value) for csres_value in allocated_csres_values
        ]
        free_ports = list(set(all_ports).difference(set(allocated_ports)))
        if len(free_ports) <= 0:
            return None
        else:
            numpy.random.shuffle(free_ports)
            return free_ports[0]
