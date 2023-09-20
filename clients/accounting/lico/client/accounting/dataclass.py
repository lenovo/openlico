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
from typing import List

import attr

logger = logging.getLogger(__name__)


@attr.s(frozen=True)
class BillGroupUserList:
    bill_group_id: int = attr.ib()
    username_list: List[str] = attr.ib(factory=list)


@attr.s(frozen=True)
class UserBillGroupMapping:
    username: str = attr.ib()
    bill_group_id: int = attr.ib()
    bill_group_name: str = attr.ib()


@attr.s(frozen=True)
class BillGroupList:
    id: int = attr.ib()
    name: str = attr.ib()


@attr.s(frozen=True)
class GreSource:
    code: str = attr.ib()
