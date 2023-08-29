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
from itertools import chain

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.response import Response

from lico.core.contrib.eventlog import EventLog
from lico.core.contrib.permissions import AsAdminRole
from lico.core.contrib.schema import json_schema_validate
from lico.core.contrib.views import APIView

from ..exceptions import (
    CreateStoragePolicyException, StoragePolicyAlreadySetException,
)
from ..models import BillGroup, BillGroupStoragePolicy

logger = logging.getLogger(__name__)


def valid_storage_info(path_list, query):
    path_list_all = set(
        chain(
            *(q.path_list for q in query.iterator())
        )
    )
    if path_list & path_list_all:
        msg = '{} has already set to storage policy '.format(path_list)
        raise StoragePolicyAlreadySetException(msg)


class StoragePolicy(APIView):
    permission_classes = (AsAdminRole,)

    @json_schema_validate({
        'type': 'object',
        'properties': {
            'path_list': {
                'type': 'array',
                "item": {
                    "type": "string",
                    'minLength': 1
                },
                "minItems": 1,
            },
            'storage_charge_rate': {
                'type': 'number',
                'minimum': 0
            }
        },
        'required': [
            'path_list',
            'storage_charge_rate'
        ]
    })
    def post(self, request, pk):
        path_list = set(request.data['path_list'])
        with transaction.atomic():
            try:
                valid_storage_info(
                    path_list,
                    BillGroupStoragePolicy.objects.filter(bill_group_id=pk)
                )
                storage = BillGroupStoragePolicy.objects.create(
                    path_list=list(path_list),
                    storage_charge_rate=request.data['storage_charge_rate'],
                    bill_group_id=pk
                )
                BillGroup.objects.filter(id=pk).update(
                    last_operation_time=timezone.now()
                )
            except IntegrityError as e:
                logger.exception('Create BillGroup Storage Policy Failed')
                raise CreateStoragePolicyException from e

        EventLog.opt_create(
            request.user.username, EventLog.billgroup, EventLog.create,
            EventLog.make_list(storage.id, 'billgroup storage policy')
        )
        return Response()


class StoragePolicyDetailView(APIView):
    permission_classes = (AsAdminRole,)

    @json_schema_validate({
        'type': 'object',
        'properties': {
            'path_list': {
                'type': 'array',
                'item': {
                    'type': 'string',
                    'minLength': 1
                },
                'minItems': 1,
            },
            'storage_charge_rate': {
                'type': 'number',
                'minimum': 0
            }
        },
        'required': [
            'path_list',
            'storage_charge_rate'
        ]
    })
    def patch(self, request, pk, storage_pk):
        path_list = set(request.data['path_list'])
        with transaction.atomic():
            try:
                obj = BillGroupStoragePolicy.objects.filter(
                    bill_group_id=pk).get(id=storage_pk)
            except BillGroupStoragePolicy.DoesNotExist:
                message = "Update storage_policy_id %s failed, " \
                          "billgroup storage policy objects " \
                          "not exist." % storage_pk
                logger.exception(message)
                raise

            valid_storage_info(
                path_list,
                BillGroupStoragePolicy.objects.filter(
                    bill_group_id=pk).exclude(pk=storage_pk)
            )
            obj.path_list = list(path_list)
            obj.storage_charge_rate = request.data['storage_charge_rate']
            obj.save()
            BillGroup.objects.filter(id=pk).update(
                last_operation_time=timezone.now()
            )
        EventLog.opt_create(
            request.user.username, EventLog.billgroup, EventLog.update,
            EventLog.make_list(storage_pk, 'billgroup storage policy')
        )
        return Response()

    def delete(self, request, pk, storage_pk):
        with transaction.atomic():
            try:
                BillGroupStoragePolicy.objects.filter(
                    bill_group_id=pk
                ).get(id=storage_pk).delete()
                BillGroup.objects.filter(id=pk).update(
                    last_operation_time=timezone.now()
                )
            except BillGroupStoragePolicy.DoesNotExist:
                message = "Delete storage_policy_id %s failed, " \
                          "BillGroupStoragePolicy objects not exist." \
                          % storage_pk
                logger.exception(message)
                raise
        EventLog.opt_create(
            request.user.username, EventLog.billgroup, EventLog.delete,
            EventLog.make_list(storage_pk, 'billgroup storage policy')
        )
        return Response()
