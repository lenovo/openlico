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


@attr.s(frozen=True)
class Node:
    hostname: str = attr.ib(kw_only=True)
    type: str = attr.ib(kw_only=True)
    on_cloud: bool = attr.ib(kw_only=True)


@attr.s(frozen=True)
class Group:
    name: str = attr.ib(kw_only=True)
    nodes: List[Node] = attr.ib(kw_only=True, factory=list)
    hostlist: List[str] = attr.ib(init=False)

    def __attrs_post_init__(self):
        object.__setattr__(
            self, 'hostlist',
            [
                node.hostname
                for node in self.nodes
            ]
        )


@attr.s(frozen=True)
class Rack:
    name: str = attr.ib(kw_only=True)
    nodes: List[Node] = attr.ib(kw_only=True, factory=list)
    hostlist: List[str] = attr.ib(init=False)

    def __attrs_post_init__(self):
        object.__setattr__(
            self, 'hostlist',
            [
                node.hostname
                for node in self.nodes
            ]
        )


@attr.s(frozen=True)
class Row:
    name: str = attr.ib(kw_only=True)
    racks: List[str] = attr.ib(kw_only=True, factory=list)

