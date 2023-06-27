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
from collections import defaultdict

from .utils import _tres_to_dict

logger = logging.getLogger(__name__)


def trans_scheduler_queue_to_dict(scheduler_queue):
    queue = {
        "name": scheduler_queue.name,
        "max_time": scheduler_queue.max_time,
        "state": scheduler_queue.state.value,
    }

    res_lists = [
        "resource_list",
        "max_resource_list",
        "per_node_resource_list",
        "used_resource_list"
    ]

    for res_list in res_lists:
        tres_str_list = []

        """"
        res_dict for example:
        {
            "gpu": {
                'G/gpu:2g:10gb': 2,
                'G/gpu:3g:20gb': 1
            }
        }
        """
        res_dict = defaultdict(dict)
        for res in getattr(scheduler_queue, res_list):
            if res.code is None:
                tres_str_list.append(_tres_to_dict(res))
                continue
            res_dict[res.code].update(_tres_to_dict(res))
        if res_dict:
            tres_str_list.extend(list(res_dict.values()))
        queue[res_list] = tres_str_list if tres_str_list else []

    return queue


def queue_has_gres(scheduler_queue, gres_code):
    for res in scheduler_queue.resource_list:
        if res.code == gres_code:
            return True
    return False
