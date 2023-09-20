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
from django.db.transaction import atomic

from lico.core.user.models import User

from . import print_green, print_red


class Command(BaseCommand):
    help = "change user's role."

    def add_arguments(self, parser):
        argument_group = parser.add_argument_group('change user role')
        argument_group.add_argument(
            '-u',
            '--username',
            required=True,
            help='user name'
        )
        argument_group.add_argument(
            '-r',
            '--role',
            required=True,
            choices=['user', 'operator', 'admin'],
            help='user role'
        )

    @atomic
    def handle(self, *args, **options):
        username = options['username']
        role = options['role']
        try:
            user = User.objects.select_for_update().get(username=username)

            if User.ROLE_NAMES[role] != user.role:
                user.role = User.ROLE_NAMES[role]
                user.save()
            print_green(f'change role to {role} finished for user {username}.')
            from lico.core.contrib.eventlog import EventLog
            EventLog.opt_create(
                'root', EventLog.user, EventLog.update,
                EventLog.make_list(user.id, username)
            )
        except User.DoesNotExist as e:
            print_red(f'User {username} does not exist.')
            raise SystemExit(-1) from e
