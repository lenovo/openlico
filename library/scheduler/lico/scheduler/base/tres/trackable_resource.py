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

from typing import Optional, Union

import attr

from .trackable_resource_type import TrackableResourceType


@attr.s(slots=True)
class TrackableResource(object):
    type: TrackableResourceType = attr.ib(default=None)
    code: Optional[str] = attr.ib(default=None)
    count: Union[int, float] = attr.ib(default=None)
    spec: Optional[str] = attr.ib(default=None)
