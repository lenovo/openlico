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

from abc import ABCMeta, abstractmethod
from typing import Optional

import attr


@attr.s(frozen=True)
class IJobIdentity(metaclass=ABCMeta):

    @abstractmethod
    def get_display(self) -> str:
        pass

    @abstractmethod
    def to_string(self) -> str:
        pass

    def to_alternative_string(self) -> Optional[str]:
        return None

    @classmethod
    @abstractmethod
    def from_string(cls, identity_str) -> 'IJobIdentity':
        pass
