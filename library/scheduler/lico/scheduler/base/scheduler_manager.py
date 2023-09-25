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

from abc import ABCMeta, abstractmethod
from typing import List

from .setting.queue_setting import QueueSetting


class ISchedulerManager(metaclass=ABCMeta):

    ####################################################################
    # Scheduler Queue
    ####################################################################
    @abstractmethod
    def query_all_queue_settings(self) -> List[QueueSetting]:
        pass

    @abstractmethod
    def query_queue_setting(self, queue_name) -> QueueSetting:
        pass

    @abstractmethod
    def create_queue_setting(self, queue_setting: QueueSetting) -> dict:
        # return value e.g.: {"is_scheduler_node": True}
        pass

    @abstractmethod
    def update_queue_setting(self, queue_setting: QueueSetting) -> dict:
        # return value e.g.: {"is_scheduler_node": True}
        pass

    @abstractmethod
    def delete_queue_setting(self, queue_name: str) -> dict:
        # return value e.g.: {"is_scheduler_node": True}
        pass

    @abstractmethod
    def update_queue_state(
            self,
            queue_name,
            queue_state: str  # QueueState.value
    ) -> dict:
        # return value e.g.: {"is_scheduler_node": True}
        pass

    ####################################################################
    # Scheduler Node
    ####################################################################
    @abstractmethod
    def query_node_state(self, node_list: str) -> dict:
        # params node_list e.g.: "c[1-2],c5"
        # return value e.g.: {
        #     "detail": ....,
        #     "node_states": {
        #         "nodes": ["c1", "c2"]
        #         "states": ["MIXRD", "IDLE+DRAIN"]
        #     }
        # }
        pass

    @abstractmethod
    def update_node_state(self, node_list: str, action: str):
        # action: ["resume", "down"]
        pass
