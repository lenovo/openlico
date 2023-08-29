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

from django.core.management.base import BaseCommand
from py.path import local


class Command(BaseCommand):
    help = 'init lico'

    def handle(self, *args, **options):
        from django.conf import settings
        from django.core.management import call_command

        from lico.core.base.models import SecretKey
        from lico.core.base.subapp import iter_sub_apps

        call_command('migrate')

        local(os.environ['LICO_LOG_FOLDER']).ensure(dir=True)
        local(os.environ['LICO_CONFIG_FOLDER']).ensure(dir=True)
        local(os.environ['LICO_STATE_FOLDER']).ensure(dir=True)
        local(os.environ['LICO_RUN_FOLDER']).ensure(dir=True)

        last = SecretKey.objects.last()
        if not last or not last.key:
            call_command('update_secret')

        for app in iter_sub_apps():
            app.on_init(settings)
