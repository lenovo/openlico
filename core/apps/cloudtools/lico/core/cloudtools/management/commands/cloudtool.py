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

import json

from django.core.management import BaseCommand
from django.db.transaction import atomic
from django.db.utils import IntegrityError

from lico.core.cloudtools.models import Tool


class Command(BaseCommand):
    help = "cloudtool operation"

    def add_arguments(self, parser):
        parser.add_argument(
            'operation',
            choices=['import', 'delete', 'list']
        )
        parser.add_argument(
            '-n', '--name', help='tool name'
        )
        parser.add_argument(
            '-c', '--code',
            help='tool code',
            nargs='?'
        )
        parser.add_argument(
            '-t', '--template', help='job template'
        )
        parser.add_argument(
            '-p', '--params', help='setting params'
        )

    @atomic
    def handle(self, *args, **options):
        code = options['code']
        operation = options['operation']

        if operation == 'import':
            if not code:
                raise SystemExit("Code can not be empty")
            try:
                Tool.objects.create(
                    name=options['name'],
                    code=code,
                    job_template=options['template'],
                    setting_params=options['params']
                )
            except IntegrityError:
                raise SystemExit(
                    f"Tool with code {options['code']} already exists"
                )
            print('Import cloud tool success.')

        elif operation == 'delete':
            if not code:
                raise SystemExit("Code can not be empty")
            tool = self._get_tool_info(code)
            tool.delete()
            print('Delete cloud tool success.')

        elif operation == 'list':
            if code:
                tool = self._get_tool_info(code)
                data = tool.as_dict(
                    include=[
                        "id", "name", "code",
                        "job_template", "setting_params"
                    ]
                )
                print(json.dumps(data, indent=4))
            else:
                for tool in Tool.objects.all().iterator():
                    print(tool.code)

    @staticmethod
    def _get_tool_info(code):
        try:
            tool = Tool.objects.get(code=code)
        except Tool.DoesNotExist:
            raise SystemExit(
                f'\033[31m{code} cloud tool does not exist\033[0m'
            )
        return tool
