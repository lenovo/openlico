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

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'update secret'

    def handle(self, *args, **options):
        from cryptography.fernet import Fernet

        from lico.core.base.models import SecretKey
        from lico.core.contrib.eventlog import EventLog

        key, created = SecretKey.objects.update_or_create(
            key=Fernet.generate_key()
        )
        if key:
            EventLog.opt_create(
                'root', 'auth', EventLog.create,
                EventLog.make_list(key.id, 'secret_key')
            )
