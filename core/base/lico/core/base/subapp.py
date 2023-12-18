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

import os
from abc import ABCMeta
from typing import Any, Dict, Iterable, List, Optional

from apscheduler.schedulers.base import BaseScheduler
from django.conf import LazySettings
from setuptools.dist import Distribution


class AbstractApplication(metaclass=ABCMeta):
    def __init__(self, name: str, dist: Distribution):
        self.name = name
        self.dist = dist

        from py.path import local
        self.settings_path = local(
            os.environ['LICO_CONFIG_FOLDER']
        ).join(
            'lico.ini.d'
        ).join(
            f'{self.name}.ini'
        )

    @property
    def active(self) -> bool:
        return not bool(self.inactive_reasons)

    @property
    def inactive_reasons(self) -> Iterable[str]:
        if not self.settings_path.exists():
            return [
                f'Config file \033[33m{self.settings_path}\033[0m not exists.',
            ]
        else:
            return []

    @property
    def config_prefix(self) -> Optional[str]:
        return self.name.upper()

    def get_root_urlconf(self, settings: LazySettings):
        return f'lico.core.{self.name}.urls'

    def on_install_apps(
            self, install_apps: List[str], arch: str
    ):
        install_apps.append(
            f'lico.core.{self.name}'
        )

    def on_install_middlewares(
            self, install_middlewares: List[str], arch: str
    ):
        pass

    def on_load_template_builtins(self, builtins: List[str], arch: str):
        pass

    def on_load_settings(
            self, settings_module_name: str, arch: str
    ):
        from .settings_toml import load_settings
        load_settings(
            settings_module_name,
            [self.settings_path],
            prefix=self.config_prefix
        )

    def on_init(self, settings: LazySettings):
        pass

    def on_load_urls(self, urlpatterns: List, settings: LazySettings):
        from django.urls import include, path

        from .views import ApplicationConfigView
        urlpatterns += [
            path(
                f'api/{self.name}/config/',
                ApplicationConfigView.as_view(app=self)
            ),
            path(
                f'api/{self.name}/',
                include(self.get_root_urlconf(settings))
            )
        ]

    def on_prepare(self, settings: LazySettings):
        pass

    def on_start(self, settings: LazySettings):
        pass

    def on_wsgi_init(self, settings: LazySettings):
        pass

    def on_config_scheduler(
            self, scheduler: BaseScheduler, settings: LazySettings
    ):
        pass

    def on_show_config(self, settings: LazySettings) -> Dict[str, Any]:
        return dict(
            name=self.name,
            project_name=self.dist.project_name,
            version=self.dist.version
        )

    def on_load_command(self, command: str):
        return True


def iter_sub_apps(
        active: Optional[bool] = True
) -> Iterable[AbstractApplication]:
    from pkg_resources import iter_entry_points
    for entry_point in iter_entry_points('lico.core.application'):
        subapp = entry_point.load()(entry_point.name, entry_point.dist)
        if active is not None:
            if subapp.active == active:
                yield subapp
        else:
            yield subapp

