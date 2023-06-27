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

from django.conf import settings
from django.core.management.base import BaseCommand

from lico.core.base.subapp import iter_sub_apps


class Command(BaseCommand):
    help = 'start lico'

    def add_arguments(self, parser):
        parser.add_argument(
            '-n', '--nodaemon', action="store_true",
            default=False,
            help='Run in the foreground'
        )
        parser.add_argument(
            '--prepare-only',
            action='store_true',
            default=False,
            help='Systemd ExecStartPre'
        )
        parser.add_argument(
            '--start-only',
            action='store_true',
            default=False,
            help='Systemd ExecStart'
        )

    def start_server(self, **options):
        import os

        from py.path import local
        from supervisor import supervisord

        args = [
            '-c',
            str(local(
                os.environ['LICO_CONFIG_FOLDER']
            ).join('lico.supervisor.ini'))
        ]
        if options['nodaemon']:
            args.append('--nodaemon')

        supervisord.main(args)

    def prepare(self):
        from django.core.management import call_command

        from lico.core.base.models import SecretKey

        last = SecretKey.objects.last()
        if not last or not last.key:
            call_command('update_secret')

        for app in iter_sub_apps():
            app.on_prepare(settings)

    def start(self, **options):
        for app in iter_sub_apps():
            app.on_start(settings)

        self.start_server(**options)

    def handle(self, *args, **options):
        if options['start_only']:
            self.start(**options)
        elif options['prepare_only']:
            self.prepare()
        else:
            self.prepare()
            self.start(**options)
