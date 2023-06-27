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

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'run supervisorctl shell'

    def handle(self, *args, **options):
        import os

        from py.path import local
        from supervisor import supervisorctl

        supervisorctl.main([
            '-c',
            str(local(
                os.environ['LICO_CONFIG_FOLDER']
            ).join('lico.supervisor.ini'))
        ])
