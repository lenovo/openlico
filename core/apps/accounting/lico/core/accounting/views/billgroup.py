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

import logging

from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.utils import timezone
from rest_framework.response import Response

from lico.core.contrib.eventlog import EventLog
from lico.core.contrib.permissions import AsAdminRole, AsOperatorRole
from lico.core.contrib.schema import json_schema_validate
from lico.core.contrib.views import APIView

from ..exceptions import (
    BillroupAlreadyExistsException, CopyBillGroupQueuePolicyException,
    CopyBillGroupStoragePolicyException, RemoveBillgroupHasMemberException,
)
from ..models import (
    BillGroup, BillGroupQueuePolicy, BillGroupStoragePolicy, Deposit,
    UserBillGroupMapping,
)
from ..utils import handle_request_data

logger = logging.getLogger(__name__)


class BillGroupListView(APIView):
    permission_classes = (AsAdminRole,)

    @AsOperatorRole
    def get(self, request):
        return Response(BillGroup.objects.all().as_dict(inspect_related=False))

    @json_schema_validate({
        'type': 'object',
        'properties': {
            'name': {
                'type': 'string',
                'minLength': 1
            },
            'charge_rate': {
                'type': 'number',
                'minimum': 0
            },
            'cr_display_type': {
                "type": "string",
                'enum': ['hour', 'minute']
            },
            'cr_minute': {
                'type': 'number',
                'minimum': 0
            },
            'balance': {
                'type': 'number',
                'minimum': 0
            },
            'description': {
                'type': 'string',
            },
            'memory_charge_rate': {
                'type': 'number',
                'minimum': 0
            },
            'mcr_display_type': {
                "type": "string",
                'enum': ['hour', 'minute']
            },
            'mcr_minute': {
                'type': 'number',
                'minimum': 0
            },
            'storage_charge_rate': {
                'type': 'number',
                'minimum': 0
            },
            'gres_charge_rate': {
                'type': 'object',
                'additionalProperties': {
                    'type': 'number',
                    'minimum': 0
                }
            },
            'gcr_display_type': {
                'type': 'object',
                'additionalProperties': {
                    'type': 'string',
                    'enum': ['hour', 'minute']
                }
            },
            'gcr_minute': {
                'type': 'object',
                'additionalProperties': {
                    'type': 'number',
                    'minimum': 0
                }
            },
        },
        'required': [
            'name',
            'charge_rate',
            'cr_display_type',
            'balance',
            'gres_charge_rate',
            'gcr_display_type',
            'memory_charge_rate',
            'mcr_display_type',
            'storage_charge_rate'
        ]
    })
    def post(self, request):
        data = handle_request_data(request.data)

        obj = BillGroup.objects.ci_exact(name=request.data.get('name'))
        if obj:
            raise BillroupAlreadyExistsException

        try:
            billgroup = BillGroup.objects.create(**data)
            timezone_now = timezone.now()
            Deposit.objects.create(
                user=request.user.username,
                bill_group=billgroup,
                credits=data['balance'],
                balance=data['balance'],
                apply_time=timezone_now,
                approved_time=timezone_now
            )
        except IntegrityError as e:
            raise BillroupAlreadyExistsException from e
        EventLog.opt_create(
            request.user.username, EventLog.billgroup, EventLog.create,
            EventLog.make_list(billgroup.id, billgroup.name)
        )
        return Response(billgroup.as_dict(inspect_related=False))


class BillGroupDetailView(APIView):
    permission_classes = (AsAdminRole,)

    def get(self, request, pk):
        try:
            obj = BillGroup.objects.get(id=pk)
        except BillGroup.DoesNotExist:
            logger.exception('BillGroup %s not exists', pk)
            raise
        data = obj.as_dict(inspect_related=False)
        data['queue_policy'] = BillGroupQueuePolicy.objects.filter(
            bill_group=obj).as_dict(inspect_related=False)
        data['storage_policy'] = BillGroupStoragePolicy.objects.filter(
            bill_group=obj).as_dict(inspect_related=False)

        return Response(data=data)

    def delete(self, request, pk):
        force = request.query_params.get('force', False)
        with transaction.atomic():
            try:
                bill_group = BillGroup.objects.get(id=pk)
                if 'true' == force and bill_group.mapping.exists():
                    UserBillGroupMapping.objects.filter(
                        bill_group=bill_group).delete()
                bill_group.delete()
            except BillGroup.DoesNotExist:
                logger.exception(
                    'Delete %s failed BillGroup objects not exist', pk)
                raise
            except ProtectedError:
                logger.exception(
                    f"Failed to delete the billing group {pk} that is "
                    f"mapping with the user")
                raise RemoveBillgroupHasMemberException
        EventLog.opt_create(
            request.user.username, EventLog.billgroup, EventLog.delete,
            EventLog.make_list(pk, bill_group.name)
        )

        return Response()

    @json_schema_validate({
        'type': 'object',
        'properties': {
            'name': {
                'type': 'string'
            },
            'charge_rate': {
                'type': 'number',
                'minimum': 0
            },
            'cr_display_type': {
                "type": "string",
                'enum': ['hour', 'minute']
            },
            'cr_minute': {
                'type': 'number',
                'minimum': 0
            },
            'description': {
                'type': 'string'
            },
            'memory_charge_rate': {
                'type': 'number',
                'minimum': 0
            },
            'mcr_display_type': {
                "type": "string",
                'enum': ['hour', 'minute']
            },
            'mcr_minute': {
                'type': 'number',
                'minimum': 0
            },
            'storage_charge_rate': {
                'type': 'number',
                'minimum': 0
            },
            'gres_charge_rate': {
                'type': 'object',
                'additionalProperties': {
                    'type': 'number',
                    'minimum': 0
                }
            },
            'gcr_display_type': {
                'type': 'object',
                'additionalProperties': {
                    'type': 'string',
                    'enum': ['hour', 'minute']
                }
            },
            'gcr_minute': {
                'type': 'object',
                'additionalProperties': {
                    'type': 'number',
                    'minimum': 0
                }
            },
        },
        'required': [
            'name',
            'charge_rate',
            'cr_display_type',
            'gres_charge_rate',
            'gcr_display_type',
            'memory_charge_rate',
            'mcr_display_type',
            'storage_charge_rate'
        ]
    })
    def patch(self, request, pk):
        data = request.data
        data = handle_request_data(data)
        try:
            BillGroup.objects.filter(id=pk).update(
                **data, last_operation_time=timezone.now()
            )
        except IntegrityError as e:
            raise BillroupAlreadyExistsException from e

        EventLog.opt_create(
            request.user.username, EventLog.billgroup, EventLog.update,
            EventLog.make_list(pk, request.data['name'])
        )
        return Response(BillGroup.objects.get(id=pk).as_dict(
            inspect_related=False)
        )

    @json_schema_validate({
        'type': 'object',
        'properties': {
            'name': {
                'type': 'string',
                'minLength': 1
            },
            'balance': {
                'type': 'number',
                'minimum': 0
            }
        },
        'required': ['name', 'balance']
    })
    def post(self, request, pk):
        exclude_fields = [
            "id", "name", "balance", "charged", "used_time",
            "used_credits", "description", "last_operation_time"
        ]
        with transaction.atomic():

            obj = BillGroup.objects.ci_exact(name=request.data['name'])
            if obj:
                raise BillroupAlreadyExistsException

            try:
                data = BillGroup.objects.get(id=pk).as_dict(
                    inspect_related=False, exclude=exclude_fields
                )
                data['name'] = request.data['name']
                data['balance'] = request.data['balance']
            except BillGroup.DoesNotExist:
                logger.exception('BillGroup %s not exists', pk)
                raise
            try:
                duplicate_bill_group = BillGroup.objects.create(**data)
            except IntegrityError as e:
                logger.exception('Bill group alreday exists')
                raise BillroupAlreadyExistsException from e

            self.create_queue_storage_policys(pk, duplicate_bill_group)
        return Response()

    def create_queue_storage_policys(self, copied_id, duplicate_bill_group):
        queue_policy_list = []
        storage_policy_list = []
        exclude_fields = [
            "id", "bill_group", "create_time", "last_operation_time"
        ]
        for q in BillGroupQueuePolicy.objects.filter(
                bill_group_id=copied_id).iterator():
            data = q.as_dict(exclude=exclude_fields)
            data["bill_group"] = duplicate_bill_group
            queue_policy_list.append(BillGroupQueuePolicy(**data))
        for s in BillGroupStoragePolicy.objects.filter(
                bill_group_id=copied_id).iterator():
            storage_policy_list.append(
                BillGroupStoragePolicy(
                    bill_group=duplicate_bill_group,
                    storage_charge_rate=s.storage_charge_rate,
                    path_list=s.path_list
                )
            )
        try:
            BillGroupQueuePolicy.objects.bulk_create(queue_policy_list)
        except IntegrityError as e:
            logger.exception('Copy Queue Policy failed.')
            raise CopyBillGroupQueuePolicyException from e
        try:
            BillGroupStoragePolicy.objects.bulk_create(storage_policy_list)
        except IntegrityError as e:
            logger.exception('Copy Storage Policy failed.')
            raise CopyBillGroupStoragePolicyException from e
