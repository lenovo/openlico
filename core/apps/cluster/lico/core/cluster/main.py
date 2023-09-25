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

from tzlocal import get_localzone

from lico.core.base.subapp import AbstractApplication


class Application(AbstractApplication):

    def on_load_settings(
        self, settings_module_name, arch
    ):
        super().on_load_settings(settings_module_name, arch)
        module = sys.modules[settings_module_name]
        module.CLUSTER.NODES_FILE = os.path.join(
            os.getenv("LICO_CONFIG_FOLDER"),
            'nodes.csv'
        )

        from lico.password import fetch_pass
        user, password = fetch_pass('confluent')
        if user is not None and password is not None:
            config = module.CLUSTER.CONFLUENT
            config.setdefault('USER', user)
            config.setdefault('PASS', password)

    def on_init(self, settings):
        if settings.CLUSTER.AUTO_SYNC_NODES:
            from .utils import clean, config, sync
            conf = config.Configure.parse(
                settings.CLUSTER.NODES_FILE
            )
            sync.sync2db(configure=conf)

            if settings.CLUSTER.SYNC_NODES_WITH_CONFLUENT:
                sync.sync2confluent(configure=conf)
                clean.cleanNodesSensitiveContent(
                    configure_file=settings.CLUSTER.NODES_FILE
                )

    def on_config_scheduler(self, scheduler, settings):
        from .tasks import delete_expired_data

        scheduler.add_job(
            func=delete_expired_data,
            trigger='cron',
            hour=0,
            max_instances=1,
            timezone=get_localzone()
        )
