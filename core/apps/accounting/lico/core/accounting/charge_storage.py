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

import logging
import os
import re
from subprocess import (
    CalledProcessError, check_call, check_output, list2cmdline,
)

from dateutil.tz import tzutc
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils.timezone import now

from lico.core.accounting.exceptions import (
    CreateDepositException, CreateStorageBillingRecordException,
    CreateStorageBillingStatementException, GetStorageQuotaFailedException,
)
from lico.core.accounting.utils import get_user_discount

from .models import (
    BillGroup, BillGroupStoragePolicy, Deposit, StorageBillingRecord,
    StorageBillingStatement, UserBillGroupMapping,
)

logger = logging.getLogger(__name__)


class StorageBilling(object):
    def __init__(self):
        self.global_path_data = {}

    def billing(self, local_date):
        billing_date = local_date.astimezone(tzutc())
        with open(os.devnull) as f:
            check_call(
                ['bash', '--login', '-c',
                 list2cmdline(
                     ['which', settings.ACCOUNTING.STORAGE.GPFS_STORAGE_CMD]
                 )],
                stdout=f, stderr=f
            )

        billing_users = []
        from lico.core.contrib.client import Client
        user_list = Client().user_client().get_user_list(
            date_joined__lte=billing_date)
        username_list = [x.username for x in user_list]
        record_user_name = StorageBillingRecord.objects.filter(
            billing_date=billing_date).values_list('username', flat=True)
        for username in username_list:
            if username in record_user_name:
                logger.info(
                    'storage was already charged for user %s on billing'
                    ' date %s.', username,
                    billing_date.strftime("%Y-%m-%d"))
            else:
                ret_flag = self._storage_charge(billing_date, username)
                if ret_flag:
                    billing_users.append(username)

        return billing_users

    def _storage_charge(self, billing_date, username):
        try:
            billgroup_user = UserBillGroupMapping.objects.get(
                username=username)
        except UserBillGroupMapping.DoesNotExist:
            logger.info(
                "user %s does not have a billgroup. "
                "Do not need to charge job.",
                username)
            return False
        storage_obj = BillGroupStoragePolicy.objects.filter(
            bill_group=billgroup_user.bill_group)
        if not storage_obj:
            self.create_storage_billing_record(billing_date, username)
            return True
        discount = get_user_discount(username)
        with transaction.atomic():
            bill_group = billgroup_user.bill_group
            for storage in storage_obj:
                for path in storage.path_list:
                    storage_count, storage_capacity = self. \
                        get_storage_count_capacity(path, username)
                    storage_cost = round(
                        storage_count * storage.storage_charge_rate, 2)
                    billing_cost = round(storage_cost * discount, 2)
                    try:
                        storage_statement = \
                            StorageBillingStatement.objects.create(
                                path=path,
                                billing_date=billing_date,
                                username=username,
                                bill_group_id=bill_group.id,
                                bill_group_name=bill_group.name,
                                storage_charge_rate=storage.
                                storage_charge_rate,
                                storage_count=storage_count,
                                storage_capacity=storage_capacity,
                                storage_cost=storage_cost,
                                discount=discount,
                                billing_cost=billing_cost
                            )
                    except IntegrityError as e:
                        logger.exception(
                            'Create StorageBillingStatement failed')
                        raise CreateStorageBillingStatementException from e
                    # To make sadsads more accurate, query again
                    bill_group = BillGroup.objects.select_for_update().get(
                        id=bill_group.id
                    )
                    bill_group.balance = round(
                        bill_group.balance - billing_cost, 2)
                    bill_group.save()
                    try:
                        Deposit.objects.create(
                            user=username,
                            bill_group=bill_group,
                            billing_type='storage',
                            credits=-billing_cost,
                            billing_id=storage_statement.id,
                            balance=bill_group.balance,
                            apply_time=storage_statement.create_time,
                            approved_time=now()
                        )
                    except IntegrityError as e:
                        logger.exception(
                            'Create StorageBillingStatement failed')
                        raise CreateDepositException from e
            self.create_storage_billing_record(billing_date, username)
            logger.info("Storage charged for user %s on billing date %s.",
                        username, billing_date)
            return True

    def create_storage_billing_record(self, billing_date, username):
        try:
            StorageBillingRecord.objects.create(
                username=username, billing_date=billing_date)
        except IntegrityError as e:
            logger.exception(
                'Create StorageBillingRecord failed')
            raise CreateStorageBillingRecordException from e

    def get_storage_count_capacity(self, path, username):
        storage_count, storage_capacity = 0, 0
        if path not in self.global_path_data:
            self.global_path_data[path] = self._check_storage(path)
        user_key = username
        if settings.ACCOUNTING.STORAGE.USER_QUOTE_IDENTITY_FIELD == 'uid':
            from lico.core.contrib.client import Client
            user_passwd = Client().auth_client().fetch_passwd(
                username=username
            )
            if user_passwd.uid is not None:
                user_key = str(user_passwd.uid)
            else:
                user_key = ''

        if user_key in self.global_path_data[path]:
            try:
                storage_count = float(
                    self.global_path_data[path][user_key][2])
                storage_capacity = float(
                    self.global_path_data[path][user_key][4])
            except ValueError:
                logger.warning(
                    "Invalid storage consume %s or capacity %s belong to %s",
                    self.global_path_data[path][user_key][2],
                    self.global_path_data[path][user_key][4],
                    username)
            # Storage unit changed from M to G
            storage_count = round(storage_count / 1024, 2)
            storage_capacity = round(storage_capacity / 1024, 2)

        return storage_count, storage_capacity

    def _check_storage(self, path):
        values = {}
        try:
            cmd = settings.ACCOUNTING.STORAGE.GPFS_STORAGE_CMD
            with open(os.devnull) as f:
                data = check_output(
                    ['bash', '--login', '-c',
                     list2cmdline([cmd, '-u', path, '--block-size', 'M'])
                     ], stderr=f)

            data = re.sub(' +', ' ', data.decode('utf-8')).strip().split('\n')
            if len(data) > 2:
                for d in data[2:]:
                    d = d.split()
                    values[d[0]] = d
            return values
        except CalledProcessError:
            logger.error('Invalid device file system: %s', path)
            return values
        except Exception as e:
            logger.exception('Get storage quota failed. Path: %s', path)
            raise GetStorageQuotaFailedException from e
