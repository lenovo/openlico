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

from os import path

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'launch beat.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--log-config',
            default=path.expandvars(
                '$LICO_CONFIG_FOLDER/lico.logging.d/base.ini'
            ),
            help='The log config file to use.'
        )

    def handle(self, *args, **options):
        import logging.config
        logging.config.fileConfig(
            options['log_config'], disable_existing_loggers=True
        )

        from apscheduler.schedulers.background import BlockingScheduler
        scheduler = BlockingScheduler()

        from django.conf import settings

        from lico.core.base.subapp import iter_sub_apps

        for app in iter_sub_apps():
            app.on_config_scheduler(scheduler, settings)

        from django import db
        db.close_old_connections()

        scheduler.start()
