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

from typing import List, Optional

import attr


@attr.s(frozen=True)
class Image:
    name: str = attr.ib(kw_only=True)
    framework: str = attr.ib(kw_only=True)
    image_path: str = attr.ib(kw_only=True)
    tags: List[str] = attr.ib(kw_only=True)
    version: Optional[str] = attr.ib(kw_only=True, default=None)
