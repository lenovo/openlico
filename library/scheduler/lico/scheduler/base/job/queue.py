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

from typing import List

import attr

from ..tres.trackable_resource import TrackableResource
from .queue_state import QueueState


@attr.s()
class Queue:
    name: str = attr.ib()
    max_time: str = attr.ib(default=None)
    state: QueueState = attr.ib(default=None)
    # total resource of the queue
    resource_list: List[TrackableResource] = attr.ib(factory=list)
    # available resource for a job
    max_resource_list: List[TrackableResource] = attr.ib(factory=list)
    # per node available resource for a job
    per_node_resource_list: List[TrackableResource] = attr.ib(factory=list)
    used_resource_list = attr.ib(factory=list)
