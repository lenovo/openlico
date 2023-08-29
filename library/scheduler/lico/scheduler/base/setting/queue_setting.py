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

from typing import List

import attr
from attr import asdict

from ..exception.manager_exception import DeserializeQueueSettingException
from ..job.queue_state import QueueState
from .queue_over_subscribe import QueueOverSubscribe


@attr.s(slots=True)
class QueueNode:
    state: str = attr.ib()               # e.g.: mix
    nodes: int = attr.ib(default=0)
    nodelist: str = attr.ib(default='')  # e.g.: c[1-2],c5


@attr.s(slots=True)
class QueueSetting:
    name: str = attr.ib()
    nodes: str = attr.ib(default=None)                  # e.g.: c[1-2],c5
    node_list: List[QueueNode] = attr.ib(factory=list)  # only for display
    default: bool = attr.ib(default=False)   # will convert to enum: YES NO
    priority: int = attr.ib(default=0)       # may not exceed 65533
    max_time: str = attr.ib(default='UNLIMITED')     # format: day-hour:minute
    over_subscribe: QueueOverSubscribe = attr.ib(default=QueueOverSubscribe())
    allow_groups: List[str] = attr.ib(factory=list)  # [] means ALL
    avail: QueueState = attr.ib(default=QueueState.UP)
    qos: str = attr.ib(default='')

    def to_dict(self):
        ret = asdict(self)

        ret['avail'] = self.avail.value
        ret['over_subscribe'] = self.over_subscribe.to_string()

        ret['nodes_total'] = {}
        ret['nodes_list'] = {}
        for n in ret.pop('node_list'):
            ret['nodes_total'][n['state']] = n['nodes']
            ret['nodes_list'][n['state']] = n['nodelist']
        return ret

    @classmethod
    def from_dict(cls, queue_info_dict):
        try:
            return QueueSetting(
                name=queue_info_dict['queue_name'],
                nodes=queue_info_dict['node_list'].replace(' ', ','),
                default=queue_info_dict.get('default', False),
                priority=int(queue_info_dict.get('priority', 0)),
                max_time=queue_info_dict.get('max_time', "UNLIMITED"),
                over_subscribe=QueueOverSubscribe.from_string(
                    queue_info_dict.get('over_subscribe', 'NO')
                ),
                allow_groups=queue_info_dict.get('user_groups', []),
                avail=QueueState[queue_info_dict.get('avail', 'UP')],
                qos=queue_info_dict.get('qos', ''),
            )
        except Exception as e:
            raise DeserializeQueueSettingException from e

    def queue_params_list(self):
        params = [
            f'PartitionName={self.name}',
            f'Nodes={self.nodes}',
            f"Default={'YES' if self.default else 'NO'}",
            f'Priority={self.priority}',
            f'MaxTime={self.max_time}',
            f'OverSubscribe={self.over_subscribe.to_string()}',
            f"AllowGroups={','.join(self.allow_groups)}",
            f"State={self.avail.value}",
            f"QoS={self.qos}",
        ]
        return params
