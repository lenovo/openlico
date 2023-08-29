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

import logging

from django.conf import LazySettings

from lico.core.base.subapp import AbstractApplication

logger = logging.getLogger(__name__)


class Application(AbstractApplication):

    def on_config_scheduler(
        self, scheduler, settings: LazySettings
    ):
        from .tasks import job_sync_task
        scheduler.add_executor(
            'processpool', alias=self.name, max_workers=1
        )
        scheduler.add_job(
            func=job_sync_task,
            trigger="interval",
            seconds=settings.JOB.JOB_SYNC_INTERVAL,
            executor=self.name,
            max_instances=1
        )

    def on_show_config(self, settings: LazySettings):
        return dict(
            name=self.name,
            project_name=self.dist.project_name,
            version=self.dist.version,
            scheduler=settings.LICO.SCHEDULER
        )
