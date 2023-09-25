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

import logging
from collections import defaultdict
from enum import Enum
from typing import Dict, List

import attr

logger = logging.getLogger(__name__)


def to_str(value):
    if type(value) is bool:
        if not value:
            return 'off'
        return 'on'
    return value


def convert_none(value):
    if value is None:
        return -1
    return value


class ResUnit(Enum):
    FIXED = 0
    PERCENTAGE = 1


@attr.s(frozen=True)
class ResUtilization:
    total: float = attr.ib(default=1.0, converter=convert_none)
    usage: float = attr.ib(default=-1, converter=convert_none)
    total_unit: ResUnit = attr.ib(default=ResUnit.FIXED)
    usage_unit: ResUnit = attr.ib(default=ResUnit.PERCENTAGE)
    index: int = attr.ib(default=-1)


@attr.s(frozen=True)
class ResData:
    hostname = attr.ib(type=str)
    status = attr.ib(type=str, converter=to_str)
    data = attr.ib(type=Dict[str, List[ResUtilization]])

    @classmethod
    def to_obj(cls, res_dict):
        resdata = cls(
            res_dict.pop('hostname'),
            res_dict.pop('status'),
            defaultdict(list)
        )
        for name, utilization in res_dict.items():
            if not utilization:
                continue
            usage_unit = ResUnit.FIXED if name == 'mem' else ResUnit.PERCENTAGE
            if type(utilization[0]) == list:
                for _index, res_util in enumerate(utilization):
                    total, usage = res_util
                    resdata.data[name].append(
                        ResUtilization(
                            total=total,
                            usage=usage,
                            usage_unit=usage_unit,
                            index=_index
                        )
                    )
            else:
                total, usage = utilization
                resdata.data[name].append(
                    ResUtilization(
                        total=total,
                        usage=usage,
                        usage_unit=usage_unit
                    )
                )
        return resdata

    def to_dict(self):
        obj_dict = attr.asdict(self)
        _dict = {
            'hostname': obj_dict['hostname'],
            'status': obj_dict['status']
        }
        for name, utils in obj_dict['data'].items():
            max_index = max([util['index'] for util in utils])
            if max_index < 0:
                _dict.update(
                    {
                        name: [utils[0]['total'], utils[0]['usage']]
                    }
                )
            else:
                res_utils = [[0, 0] for _index in range(max_index+1)]
                for util in utils:
                    res_utils[util['index']] = [util['total'], util['usage']]
                _dict.update({name: res_utils})
        return _dict
