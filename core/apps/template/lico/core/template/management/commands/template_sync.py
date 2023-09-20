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

from django.conf import settings
from django.core.management.base import BaseCommand

__all__ = ['Command']


class Command(BaseCommand):
    help = 'Sync public template to lico db.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--templatepath', nargs='+',
            default=settings.TEMPLATE.TEMPLATE_PATH,
            help='The public template path'
        )

    def handle(self, *args, **options):
        from os import path
        templatepath = options['templatepath']

        for p in templatepath:
            if not path.exists(p):
                print(f'Templatepath {p} not available')
                exit(1)

        from lico.core.template.utils.templates import sync

        sync(templatepath)

        from lico.core.template.models import Template
        for template in Template.objects.iterator():
            print(template.code)

