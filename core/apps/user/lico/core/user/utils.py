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

import csv
import logging
import operator
import pwd

from django.conf import settings
from django.db.transaction import atomic
from rest_framework.exceptions import PermissionDenied

from lico.core.contrib.eventlog import EventLog

from .exceptions import (
    FileFormatInvalid, TitleFieldsInvalid, UserDuplicate, UserEmpty,
    UserRoleInvalid,
)
from .models import ImportRecord, User

logger = logging.getLogger(__name__)


def require_libuser(func):
    def wrapper(*args, **kwargs):
        if not settings.USER.USE_LIBUSER:
            raise PermissionDenied
        return func(*args, **kwargs)
    return wrapper


def validate_import_record_title(titles):
    try:
        necessary_titles = sorted(
            ['username', 'role', 'last_name', 'first_name', 'email']
        )
        intersection = sorted(list(
            set(necessary_titles).intersection(set(titles))
        ))
        return operator.eq(intersection, necessary_titles)
    except Exception:
        return False


@atomic
def create_import_records(byte_stream, task):
    assigned_username_set = set()
    import_records = []
    try:
        import io

        import chardet
        content = byte_stream.read()
        encoding = chardet.detect(content)['encoding']
        reader = csv.DictReader(
            io.StringIO(
                content.decode(
                    encoding if encoding == 'utf-8' else 'gbk'
                )
            )
        )
        titles = reader.fieldnames
    except Exception as e:
        logger.exception("csv operation error!")
        raise FileFormatInvalid from e

    if not validate_import_record_title(titles):
        logger.exception("Title fields invalid.")
        raise TitleFieldsInvalid

    for line_no, row in enumerate(reader, start=1):
        row_data = {
            k.strip(): v.strip()
            for k, v in row.items()
        }
        username = row_data["username"]
        if not username:
            logger.exception("username cannot be empty.")
            raise UserEmpty

        if username in assigned_username_set:
            logger.exception("username already exists.")
            raise UserDuplicate

        try:
            role = User.ROLE_NAMES[row_data["role"].lower()]
        except KeyError as e:
            logger.exception("The role does not exist.")
            raise UserRoleInvalid from e
        import_records.append(ImportRecord(
            row=line_no,
            username=username,
            role=role,
            last_name=row_data["last_name"],
            first_name=row_data["first_name"],
            email=row_data["email"],
            task=task
        ))
        assigned_username_set.add(username)
    ImportRecord.objects.bulk_create(import_records)


def import_record(task, operator_username='root'):
    try:
        with atomic():
            for record in task.records.order_by("row"):
                task.refresh_from_db()
                if not task.is_running:
                    raise Exception(
                        "Import record process is terminated"
                    )

                try:
                    pwd.getpwnam(record.username)
                except KeyError:
                    record.ret = False
                    record.error_message = 'The user does not exist in nss.'
                    record.save()
                    continue

                if User.objects.filter(username=record.username).exists():
                    record.ret = False
                    record.error_message = 'The user already exists in db.'
                    record.save()
                    continue

                user = User.objects.create(
                    username=record.username,
                    first_name=record.first_name,
                    last_name=record.last_name,
                    email=record.email,
                    role=record.role
                )
                record.ret = True
                record.save()
                EventLog.opt_create(
                    operator_username,
                    EventLog.user,
                    EventLog.create,
                    EventLog.make_list(user.id, user.username)
                )
    except Exception:
        logger.exception("Import record failed.")
        raise
    finally:
        task.is_running = False
        task.save()


def users_billing_group():
    from lico.core.contrib.client import Client
    try:
        client = Client().accounting_client()
    except AttributeError:
        logger.info(
            "Can not find lico-accounting-client", exc_info=True
        )
        return []
    return client.get_user_bill_group_mapping()
