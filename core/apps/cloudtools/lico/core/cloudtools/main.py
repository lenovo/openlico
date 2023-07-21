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

from typing import List

from django.conf import LazySettings

from lico.core.base.subapp import AbstractApplication


class Application(AbstractApplication):

    def on_load_urls(self, urlpatterns: List, settings: LazySettings):
        from django.urls import path

        super().on_load_urls(urlpatterns, settings)

        from .views.views import ShareView
        urlpatterns += [
            path(f'{self.name}/', ShareView.as_view())
        ]
