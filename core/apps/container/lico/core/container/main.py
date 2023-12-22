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

import sys
from typing import List

from django.conf import LazySettings

from lico.core.base.subapp import AbstractApplication

from .exceptions import UnknowError


class Application(AbstractApplication):

    def get_root_urlconf(self, settings: LazySettings):
        if settings.LICO.ARCH == 'host':
            return f'lico.core.{self.name}.singularity.urls'
        else:
            raise UnknowError

    def on_install_apps(
        self, install_apps: List[str], arch: str
    ):
        if arch == 'host':
            install_apps.append(
                f'lico.core.{self.name}.singularity'
            )

    def on_load_settings(
            self, settings_module_name: str, arch: str
    ):
        super().on_load_settings(settings_module_name, arch)

        if arch == 'host':
            module = sys.modules[settings_module_name]
            module.CONTAINER.setdefault(
                'AI_CONTAINER_ROOT', '/home/lico/container'
            )

    def on_prepare(self, settings):
        if settings.LICO.ARCH == 'host':
            from .singularity.models import SingularityImage
            from .singularity.utils import TaskStatus
            SingularityImage.objects.exclude(
                status__in=[
                    TaskStatus.SUCCESS.value,
                    TaskStatus.FAILURE.value
                ]
            ).update(status=TaskStatus.FAILURE.value)
