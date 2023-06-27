# -*- coding: utf-8 -*-
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

from typing import Any, Dict, List


def get_one(multi_dict: Dict, key: str) -> Any:
    """Return one value matching the key in the dict.

    Raise KeyError if multiple values were found.
    """
    matched = [v for k, v in multi_dict.items() if k == key]
    if len(matched) > 1:
        raise KeyError(
            "{} matched more than one key in {}".format(key, multi_dict)
        )
    return next(iter(matched), None)


def get_all(multi_dict: Dict, key: str) -> List[Any]:
    """Return a list with all values matching the key in the dict.

    May return an empty list.
    """
    for k, v in multi_dict.items():
        if k == key:
            if not isinstance(v, list):
                v = [v]
            return v
    return []
