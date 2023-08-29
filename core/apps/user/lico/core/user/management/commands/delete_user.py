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
from django.db.transaction import atomic

from lico.core.user.database import DataBase
from lico.core.user.exceptions import InvalidOperation
from lico.core.user.libuser import Libuser
from lico.core.user.models import User

from . import print_green, print_red


class Command(BaseCommand):
    help = 'delete user'

    def add_arguments(self, parser):
        argument_group = parser.add_argument_group('delete user')
        argument_group.add_argument(
            '-u', '--username', required=True,
            help='user name'
        )

    @atomic
    def handle(self, *args, **options):
        username = options['username']
        try:
            delete_user = DataBase().get_user(username, lock=True)
        except User.DoesNotExist as e:
            print_red(f'User {username} does not exist.')
            raise SystemExit(-1) from e
        if settings.USER.USE_LIBUSER:
            try:
                Libuser().remove_user(delete_user.username)
            except InvalidOperation as e:
                print_red(f'Failed to delete {username} from LDAP.')
                raise SystemExit(-1) from e
        delete_user_id = delete_user.id
        delete_user.delete()
        print_green(f'Successfully delete {username}')
        from lico.core.contrib.eventlog import EventLog
        EventLog.opt_create(
            'root', EventLog.user, EventLog.delete,
            EventLog.make_list(delete_user_id, username)
        )
