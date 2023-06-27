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

from functools import lru_cache
from typing import Callable


class Client:
    import re
    _pattern = re.compile(r'^(?P<name>.+)_client$')

    @staticmethod
    @lru_cache(maxsize=None)
    def _get_client_func(name, arch):
        from pkg_resources import iter_entry_points

        for entry_point in iter_entry_points('lico.core.client'):
            if entry_point.name == name:
                return entry_point.load()

        for entry_point in iter_entry_points(
            f'lico.core.{arch}.client'
        ):
            if entry_point.name == name:
                return entry_point.load()

        raise AttributeError(
            f"'Client' object has no attribute '{name}'"
        )  # pragma: no cover

    def __getattr__(self, item: str) -> Callable:
        result = self._pattern.match(item)

        if result is not None:
            from django.conf import settings
            return self._get_client_func(
                name=result.groupdict()['name'],
                arch=settings.LICO.ARCH
            )(settings)

        raise AttributeError(
            f"'Client' object has no attribute '{item}'"
        )  # pragma: no cover
