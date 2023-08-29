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

import pwd

from django.core.management import BaseCommand
from django.db.transaction import atomic
from django.db.utils import IntegrityError
from py.path import local

from lico.core.user.models import ImportRecordTask, User
from lico.core.user.utils import create_import_records, import_record

from . import print_green, print_red


class Command(BaseCommand):
    help = 'Import user(s) from nss to db.'

    def add_arguments(self, parser):
        argument_group = parser.add_argument_group('import user')
        argument_group.add_argument(
            '-u', '--username', required=False,
            help='user name'
        )
        argument_group.add_argument(
            '-r', '--role', default='user',
            choices=['user', 'operator', 'admin'],
            help='user role'
        )
        argument_group.add_argument(
            '-f', '--filename', required=False,
            help='batch import users from csv file'
        )

    def handle(self, *args, **options):
        filename = options.get("filename")
        username = options.get("username")
        if filename and not username:
            return self._batch_import_user(local(filename))
        elif username and not filename:
            return self._import_user(
                username, options["role"]
            )
        else:
            print_red(
                "one of the arguments -u -f is required"
            )
            raise SystemExit(-1)

    @staticmethod
    def _import_user(username, role):
        try:
            pwd.getpwnam(username)
        except KeyError as e:
            print_red(
                f'Error: User {username} does not exist in nss.'
            )
            raise SystemExit(-1) from e

        try:
            User.objects.create(
                username=username,
                role=User.ROLE_NAMES[role]
            )
        except IntegrityError as e:
            print_red(
                f'Error: User {username} has already existed in db.')
            raise SystemExit(-1) from e
        print_green("Import user finished")

    @staticmethod
    @atomic
    def _batch_import_user(filename):
        if not filename.isfile():
            print_red(f'Error: The {filename} not a file')
            raise SystemExit(-1)
        try:
            exists_task = ImportRecordTask.objects.select_for_update(
            ).get(owner="root")
            if exists_task.is_running:
                print_red("Running work exists")
                raise SystemExit(-1)
            else:
                exists_task.delete()
        except ImportRecordTask.DoesNotExist:
            pass
        task = ImportRecordTask.objects.create(owner="root")
        try:
            with filename.open(mode='rb') as f:
                create_import_records(f, task)
            import_record(task)
        except Exception as e:
            print_red('Error: An exception occurred during the import')
            raise SystemExit(-1) from e
        print_green("Import user finished")
