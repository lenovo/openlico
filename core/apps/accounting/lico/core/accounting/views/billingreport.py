# -*- coding: utf-8 -*-
# Copyright 2019-present Lenovo
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

from django.conf import settings
from django.db.models import Max
from django.http import StreamingHttpResponse
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from lico.core.contrib.schema import json_schema_validate
from lico.core.contrib.views import APIView

from ..exceptions import (
    BillingFileNotFoundException, BillingNotGenerateException,
    InvalidParameterException,
)
from ..models import BillingFile

logger = logging.getLogger(__name__)


class BillingDate(APIView):
    def get(self, request):
        if 'billing_type' not in request.query_params:
            raise InvalidParameterException

        billing_type = request.query_params['billing_type']

        filter_data = {
            "billing_type": billing_type,
        }

        if billing_type == 'cluster':
            if not request.user.is_admin:
                raise PermissionDenied(detail='Incorrect user role.')
        elif billing_type == 'user':
            filter_data["username"] = request.user.username

        latest_daily = BillingFile.objects.filter(
            period='daily',
            **filter_data
        ).aggregate(Max("billing_date"))
        latest_monthly = BillingFile.objects.filter(
            period='monthly',
            **filter_data
        ).aggregate(Max("billing_date"))

        data = {
            "latest_daily": latest_daily['billing_date__max'],
            "latest_monthly": latest_monthly['billing_date__max']
        }

        return Response(data)


class BillingDownload(APIView):
    @json_schema_validate({
        'type': 'object',
        'properties': {
            'billing_type': {
                'type': 'string',
                'minLength': 1,
                'enum': ['cluster', 'user']
            },
            'period': {
                'period': 'string',
                'minimum': 1,
                'enum': ['daily', 'monthly']
            },
            'billing_date': {
                'type': 'string',
                'minimum': 1,
                "pattern": r"\d{4}-\d{1,2}-\d{1,2}"
            },
        },
        'required': [
            'billing_type',
            'period',
            'billing_date'
        ]
    })
    def post(self, request):

        billing_type = request.data['billing_type']
        period = request.data['period']
        billing_date = request.data['billing_date']

        filter_data = {
            'billing_type': billing_type,
            'period': period,
        }

        if billing_type == 'cluster':
            if not request.user.is_admin:
                raise PermissionDenied(detail='Incorrect user role.')
        elif billing_type == 'user':
            filter_data['username'] = request.user.username

        if period == 'daily':
            filter_data['billing_date'] = billing_date
        elif period == 'monthly':
            (filter_data['billing_date__year'],
             filter_data['billing_date__month'],
             _) = billing_date.split("-", 3)
        billingfile = BillingFile.objects.filter(**filter_data).last()

        if not billingfile:
            logger.exception('Billing is not generated.')
            raise BillingNotGenerateException

        file_path = os.path.join(
            settings.ACCOUNTING.BILLING_DIR, billingfile.filename)
        if not os.path.isfile(file_path):
            logger.exception('Billing file not found.')
            raise BillingFileNotFoundException

        response = StreamingHttpResponse(open(file_path, 'rb'))
        response['Content-Type'] = 'application/octet-stream'
        response['Content-Disposition'] = \
            f'attachement;filename="{billingfile.filename}"'
        return response
