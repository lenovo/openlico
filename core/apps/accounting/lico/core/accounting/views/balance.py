# Copyright 2023-present Lenovo
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

from django.db.transaction import atomic
from rest_framework.response import Response

from lico.core.alert.models import NotifyTarget
from lico.core.contrib.permissions import AsAdminRole
from lico.core.contrib.schema import json_schema_validate
from lico.core.contrib.views import APIView

from ..exceptions import UpdateBalanceAlertException
from ..models import BalanceAlert, BalanceAlertSetting, BillGroup

logger = logging.getLogger(__name__)


class BalanceView(APIView):
    permission_classes = (AsAdminRole,)

    def get(self, request):
        balance_setting = BalanceAlertSetting.objects.first().as_dict()
        targets = balance_setting.pop('targets')
        balance_setting['targets'] = []
        for target in targets:
            balance_setting['targets'].append(target.get('id'))
        return Response(balance_setting)

    @json_schema_validate({
        'type': 'object',
        'properties': {
            'balance_threshold': {
                'type': 'number',
                'minimum': 0
            },
            'targets': {
                'type': 'array',
                'items': {
                    'type': 'integer'
                }
            }
        },
        'required': ['balance_threshold', 'targets']
    })
    @atomic
    def put(self, request):
        balance = request.data['balance_threshold']
        balance_setting = BalanceAlertSetting.objects.first()
        query_s = NotifyTarget.objects.filter(
            id__in=request.data.get('targets', [])
        )
        original_balance_threshold = balance_setting.balance_threshold
        balance_setting.balance_threshold = balance
        balance_setting.targets.set(query_s)
        balance_setting.save()
        if balance_setting.balance_threshold != original_balance_threshold:
            BalanceAlert.objects.all().delete()
        return Response(balance_setting.as_dict())


class BalanceAlertView(APIView):
    permission_classes = (AsAdminRole,)

    @json_schema_validate({
        'type': 'object',
        'properties': {
            'balance_alert': {
                'type': 'boolean'
            }
        },
        'required': ['balance_alert']
    })
    @atomic
    def put(self, request, pk):
        try:
            bill_group = BillGroup.objects.get(id=pk)
            bill_group.balance_alert = request.data['balance_alert']
            bill_group.save()
            return Response({})
        except BillGroup.DoesNotExist:
            raise
        except Exception as e:
            raise UpdateBalanceAlertException from e
