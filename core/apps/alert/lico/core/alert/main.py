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
import sys

import pkg_resources

from lico.core.base.subapp import AbstractApplication


class Application(AbstractApplication):
    def on_load_settings(
            self, settings_module_name, arch
    ):
        super().on_load_settings(settings_module_name, arch)
        module = sys.modules[settings_module_name]
        module.ALERT.setdefault(
            'SCRIPTS_DIR',
            os.path.join(
                os.getenv("LICO_STATE_FOLDER"),
                'alert', 'scripts'
            )
        )
        notificaitons = list()
        for entry_point in pkg_resources.iter_entry_points(
                'lico.core.alert.notifications'):
            notificaitons.append(entry_point.load())
        module.ALERT.NOTIFICATIONS = notificaitons

    def on_config_scheduler(self, scheduler, settings):
        from .tasks import (
            cpu_scanner, disk_scanner, energy_scanner, gpu_mem_scanner,
            gpu_temp_scanner, gpu_util_scanner, hardware_dis_scanner,
            hardware_scanner, memory_scanner, node_active, temp_scanner,
        )

        funcs = (
            cpu_scanner, disk_scanner, energy_scanner, temp_scanner,
            hardware_scanner, node_active, gpu_mem_scanner, gpu_temp_scanner,
            gpu_util_scanner, memory_scanner, hardware_dis_scanner
        )
        scheduler.add_executor(
            'processpool', alias=self.name, max_workers=len(funcs)
        )

        for func in funcs:
            scheduler.add_job(
                func=func,
                trigger='cron',
                second='*/30',
                max_instances=1,
                executor=self.name,
            )

