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

import os
import sys

from lico.core.base.subapp import AbstractApplication


class Application(AbstractApplication):
    def on_load_template_builtins(self, builtins, arch):
        builtins += [
            "lico.core.template.templatetags",
            "lico.core.template.templatetags.common",
            "lico.core.template.templatetags.devtools",
            "lico.core.template.templatetags.lsf",
            "lico.core.template.templatetags.pbs",
            "lico.core.template.templatetags.host",
        ]

    def on_load_settings(
        self, settings_module_name, arch
    ):
        super().on_load_settings(settings_module_name, arch)
        module = sys.modules[settings_module_name]
        module.TEMPLATE.setdefault(
            'TEMPLATE_PATH',
            [
                os.path.join(os.environ["LICO_STATE_FOLDER"], 'templates')
            ]
        )

    def on_init(self, settings):
        from django.core.management import call_command
        call_command('lmod_sync')
        call_command('template_sync')
