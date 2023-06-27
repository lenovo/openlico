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
    CreateQueuePolicyException, QueuePolicyAlreadySetException,
)
from ..models import BillGroup, BillGroupQueuePolicy
from ..utils import handle_request_data

logger = logging.getLogger(__name__)


def valid_queue_info(queue_list, query):
    queue_list_all = set(
        chain(
            *(q.queue_list for q in query.iterator())
        )
    )

    if queue_list & queue_list_all:
        msg = '{} has already set to queue policy '.format(queue_list)
        raise QueuePolicyAlreadySetException(msg)


class QueuePolicyView(APIView):
    permission_classes = (AsAdminRole,)

    @json_schema_validate({
        'type': 'object',
        'properties': {
            'bill_group': {
                'type': 'integer'
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
            'queue_list': {
                'type': 'array',
                "items": {
                    "type": "string",
                    'minLength': 1
                },
                'minItems': 1
            }
        },
        'required': [
            'charge_rate',
            'cr_display_type',
            'gres_charge_rate',
            'gcr_display_type',
            'memory_charge_rate',
            'mcr_display_type',
            'queue_list'
        ]
    })
    def post(self, request, pk):
        queue_list = set(request.data['queue_list'])
        data = handle_request_data(request.data)
        data["queue_list"] = list(queue_list)
        data["bill_group_id"] = pk
        with transaction.atomic():
            try:
                valid_queue_info(
                    queue_list,
                    BillGroupQueuePolicy.objects.filter(bill_group_id=pk)
                )
                queue_policy = BillGroupQueuePolicy.objects.create(**data)
                BillGroup.objects.filter(id=pk).update(
                    last_operation_time=timezone.now()
                )
            except IntegrityError as e:
                logger.exception("Create BillGroup Queue Policy Failed")
                raise CreateQueuePolicyException from e

        EventLog.opt_create(
            request.user.username, EventLog.billgroup, EventLog.create,
            EventLog.make_list(
                queue_policy.id, 'billgroup queue policy'
            )
        )
        return Response()


class QueuePolicyDetailView(APIView):
    permission_classes = (AsAdminRole,)

    @json_schema_validate({
        'type': 'object',
        'properties': {
            'bill_group': {
                'type': 'integer'
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
            'queue_list': {
                'type': 'array',
                "items": {
                    "type": "string",
                    'minLength': 1
                },
                'minItems': 1
            }
        },
        'required': [
            'charge_rate',
            'cr_display_type',
            'gres_charge_rate',
            'gcr_display_type',
            'memory_charge_rate',
            'mcr_display_type',
            'queue_list'
        ]
    })
    def patch(self, request, pk, policy_pk):
        queue_list = set(request.data['queue_list'])
        data = handle_request_data(request.data)
        with transaction.atomic():
            try:
                obj = BillGroupQueuePolicy.objects.filter(
                    bill_group_id=pk
                ).get(id=policy_pk)
            except BillGroupQueuePolicy.DoesNotExist:
                message = "Update queue_policy_id {} failed, " \
                          "billgroup queue policy objects " \
                          "not exist.".format(policy_pk)
                logger.exception(message)
                raise

            valid_queue_info(
                queue_list,
                BillGroupQueuePolicy.objects.filter(
                    bill_group_id=pk
                ).exclude(
                    pk=policy_pk
                )
            )
            obj.charge_rate = data['charge_rate']
            obj.cr_minute = data['cr_minute']
            obj.cr_display_type = data['cr_display_type']
            obj.gres_charge_rate = data['gres_charge_rate']
            obj.gcr_minute = data['gcr_minute']
            obj.gcr_display_type = data['gcr_display_type']
            obj.memory_charge_rate = data['memory_charge_rate']
            obj.mcr_minute = data['mcr_minute']
            obj.mcr_display_type = data['mcr_display_type']
            obj.queue_list = list(queue_list)

            obj.save()
            BillGroup.objects.filter(id=pk).update(
                last_operation_time=timezone.now()
            )
        EventLog.opt_create(
            request.user.username, EventLog.billgroup, EventLog.update,
            EventLog.make_list(policy_pk, 'billgroup queue policy')
        )

        return Response()

    def delete(self, request, pk, policy_pk):
        with transaction.atomic():
            try:
                BillGroupQueuePolicy.objects.filter(
                    bill_group_id=pk
                ).get(id=policy_pk).delete()
                BillGroup.objects.filter(id=pk).update(
                    last_operation_time=timezone.now()
                )
            except BillGroupQueuePolicy.DoesNotExist:
                message = "Delete queue_policy_id {} failed, " \
                          "billgroup queue policy objects " \
                          "not exist.".format(policy_pk)
                logger.exception(message)
                raise
        EventLog.opt_create(
            request.user.username, EventLog.billgroup, EventLog.delete,
            EventLog.make_list(policy_pk, 'billgroup queue policy')
        )

        return Response()
