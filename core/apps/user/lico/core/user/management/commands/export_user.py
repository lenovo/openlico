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

from lico.core.user.models import User
from lico.core.user.utils import users_billing_group


class Command(BaseCommand):

    def add_arguments(self, parser):

        parser.add_argument(
            '-f',
            '--filename',
            required=True,
            help='the FILENAME is the name of the file that will be exported'
        )

    def handle(self, *args, **options):
        from django.template.loader import render_to_string

        filename = options['filename']

        users_bill_group = users_billing_group()

        user_info = render_to_string(
            "user/export.csv",
            context={
                "users": User.objects.all(),
                "users_bill_group": users_bill_group
            }
        )
        with open(filename, "w") as f:
            f.write(user_info)
