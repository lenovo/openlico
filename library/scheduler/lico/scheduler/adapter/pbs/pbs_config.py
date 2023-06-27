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

import attr

from lico.scheduler.base.scheduler_config import BaseSchedulerConfig


@attr.s(slots=True, frozen=True)
class SchedulerConfig(BaseSchedulerConfig):
    tracking_gres_list = attr.ib(default=['gpu'])
    cmd_out_places = attr.ib(default=40)
    memory_retry_count = attr.ib(default=1)
    memory_retry_interval_second = attr.ib(default=0.5)
