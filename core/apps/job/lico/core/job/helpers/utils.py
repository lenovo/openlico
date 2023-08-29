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

from lico.scheduler.base.tres.trackable_resource_type import (
    TrackableResourceType,
)

logger = logging.getLogger(__name__)


def _tres_to_dict(tres):
    type_code = _tres_type_mapping(tres.type)
    if tres.code is not None and len(tres.code) > 0:
        type_code = type_code + '/' + tres.code
        if tres.spec is not None:
            type_code = type_code + ':' + tres.spec
    return {type_code: str(tres.count)}


def _tres_to_str(tres):
    type_code = _tres_type_mapping(tres.type)
    if tres.code is not None and len(tres.code) > 0:
        return type_code + '/' + tres.code + (
            ("/" + tres.spec) if tres.spec else "") + ':' + str(tres.count)
    else:
        return type_code + ':' + str(tres.count)


def _tres_type_mapping(tres_type):
    switch = {
        TrackableResourceType.NODES: "N",
        TrackableResourceType.CORES: "C",
        TrackableResourceType.MEMORY: "M",
        TrackableResourceType.LICENSE: "L",
        TrackableResourceType.GRES: "G"
    }
    try:
        return switch[tres_type]
    except KeyError:
        return "UN"


def _none_str_filter(maybe_none_str):
    if maybe_none_str is None:
        return ''
    else:
        return maybe_none_str


def _tres_list_to_dict(tres_list):
    # tres_list sample: ["M:2.13", "N:1", "C:4.0", "G/gpu:1.0"]
    tres_dict = {}
    for tres in tres_list:
        item = tres.split(":")
        if len(item) == 2:
            tres_dict[item[0]] = item[1]
        else:
            logger.warning("Unknown tres format: {0}".format(tres_list))

    return tres_dict
