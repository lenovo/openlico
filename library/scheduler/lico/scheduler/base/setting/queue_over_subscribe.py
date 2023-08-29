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
from enum import Enum

import attr

from ..exception.manager_exception import DeserializeOverSubscribeException

logger = logging.getLogger(__name__)


class OverSubscribeType(Enum):
    EXCLUSIVE = "EXCLUSIVE"
    FORCE = "FORCE"
    YES = "YES"
    NO = "NO"


@attr.s(slots=True)
class QueueOverSubscribe:
    type: OverSubscribeType = attr.ib(default=OverSubscribeType.NO)
    job_count: int = attr.ib(default=None)

    def to_string(self):
        ret = self.type.value
        if self.job_count is not None:
            ret += f':{self.job_count}'
        return ret

    @classmethod
    def from_string(cls, over_subscribe_str):
        try:
            split_list = over_subscribe_str.split(":")
            job_count = None
            if len(split_list) == 1:
                type = split_list[0]
            elif len(split_list) == 2:
                type = split_list[0]
                job_count = int(split_list[1])
            else:
                raise

            return QueueOverSubscribe(
                type=OverSubscribeType[type],
                job_count=job_count
            )
        except Exception as e:
            logger.exception(
                "Deserialize string '%s' to QueueOverSubscribe failed.",
                over_subscribe_str
            )
            raise DeserializeOverSubscribeException from e
