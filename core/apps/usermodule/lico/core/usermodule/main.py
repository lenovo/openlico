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

import pkg_resources

from lico.core.base.subapp import AbstractApplication


class Application(AbstractApplication):
    def on_load_settings(
            self, settings_module_name, arch
    ):
        super().on_load_settings(settings_module_name, arch)
        module = sys.modules[settings_module_name]
        easybuildutils = dict()
        for entry_point in pkg_resources.iter_entry_points(
                'lico.core.usermodule.easybuildutils'):
            easybuildutils[entry_point.name] = entry_point.load()
        module.USERMODULE.EASYBUILDUTILS = easybuildutils
