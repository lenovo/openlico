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

from lico.core.base.subapp import AbstractApplication


class Application(AbstractApplication):
    def on_config_scheduler(self, scheduler, settings):
        from .tasks import heartbeat_scanner
        scheduler.add_executor(
            'processpool', alias=self.name, max_workers=1
        )
        scheduler.add_job(
            func=heartbeat_scanner,
            trigger='cron',
            second='*/15',
            max_instances=1,
            executor=self.name,
        )
