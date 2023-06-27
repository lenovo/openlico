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

import importlib
from typing import List

from django.conf import LazySettings

from lico.core.base.subapp import AbstractApplication


class Application(AbstractApplication):
    def get_root_urlconf(self, settings: LazySettings):
        return f'lico.core.{self.name}_{settings.LICO.ARCH}.urls'

    def on_install_apps(
        self, install_apps: List[str], arch: str
    ):
        super().on_install_apps(install_apps, arch)
        install_apps.append(
            f'lico.core.{self.name}_{arch}'
        )

    def on_load_urls(self, urlpatterns: List, settings: LazySettings):
        super().on_load_urls(urlpatterns, settings)
        from django.urls import include, path

        from . import urls as mixed_urls
        urlpatterns += [
            path(
                f'api/{self.name}/',
                include(mixed_urls)
            )
        ]

    def on_init(self, settings):
        app = importlib.import_module(
            f'lico.core.{self.name}_{settings.LICO.ARCH}.app'
        )
        app.on_init(self, settings)

    def on_config_scheduler(self, scheduler, settings):
        app = importlib.import_module(
            f'lico.core.{self.name}_{settings.LICO.ARCH}.app'
        )
        app.on_config_scheduler(self, scheduler, settings)

    def on_show_config(self, settings):
        config = super().on_show_config(settings)
        config['targets'] = settings.MONITOR.TARGETS
        return config
