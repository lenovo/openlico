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
import pkg_resources
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'launch celery worker.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--log-level', default='INFO',
            choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL', 'FATAL'],
            help='Logging level'
        )
        parser.add_argument(
            '--autoscale', required=True,
            help='Enable autoscaling by providing '
                 'max_concurrency,min_concurrency'
        )

    def handle(self, *args, **options):
        from lico.core.base.celery import app

        try:
            if pkg_resources.require("celery >= 5.0"):
                argv = ['worker', '-l', options['log_level'],
                        '--autoscale', options['autoscale']]
        except pkg_resources.VersionConflict:
            argv = ['celery', 'worker', '-l', options['log_level'],
                    '--autoscale', options['autoscale']]

        app.start(argv)
