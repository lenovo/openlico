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

from datetime import datetime, timedelta
from os import path

from dateutil.tz import tzoffset
from django.db import transaction
from django.db.models import Q
from django.http import StreamingHttpResponse
from django.utils import timezone
from rest_framework.response import Response

from lico.core.contrib.eventlog import EventLog
from lico.core.contrib.permissions import AsAdminRole
from lico.core.contrib.schema import json_schema_validate
from lico.core.contrib.views import APIView, DataTableView

from ..exceptions import InvalidParameterException
from ..helpers.deposit_report_helper import (
    DepositReportExporter, format_datetime,
)
from ..models import (
    BillGroup, Deposit, JobBillingStatement, StorageBillingStatement,
)
from ..utils import set_language, trans_billing_type


class DepositListView(APIView):
    permission_classes = (AsAdminRole,)

    def get(self, request):
        return Response(Deposit.objects.all().as_dict())

    @json_schema_validate({
        'type': 'object',
        'properties': {
            'user': {
                'type': 'string'
            },
            'bill_group': {
                'type': 'integer',
                'minimum': 0
            },
            'credits': {
                'type': 'number',
            }
        },
        'required': ['user', 'bill_group', 'credits']
    })
    def post(self, request):
        with transaction.atomic():
            bill_group = BillGroup.objects.get(id=request.data['bill_group'])
            timezone_now = timezone.now()
            deposit = Deposit.objects.create(
                user=request.data['user'],
                bill_group=bill_group,
                credits=float(request.data['credits']),
                balance=round(bill_group.balance + request.data['credits'], 2),
                apply_time=timezone_now,
                approved_time=timezone_now)
            bill_group.balance += deposit.credits
            bill_group.balance = round(bill_group.balance, 2)
            bill_group.save()

        EventLog.opt_create(
            request.user.username, EventLog.deposit,
            DespositEventLog.action(deposit.credits),
            EventLog.make_list(
                deposit.id, '{0} {1:0.2f}'.format(bill_group.name,
                                                  abs(deposit.credits))))
        return Response(deposit.as_dict())


class DepositDetailView(APIView):
    permission_classes = (AsAdminRole,)

    def get(self, request, pk):
        return Response(Deposit.objects.get(id=pk).as_dict())

    def delete(self, request, pk):
        Deposit.objects.get(id=pk).delete()
        return Response()


class DepositListDetailView(DataTableView):
    permission_classes = (AsAdminRole,)
    bill_group_id = None

    def global_search(self, query, param_args):
        if 'search' not in param_args or query is None:
            return query
        search = param_args['search']
        props = search['props']
        keyword = search['keyword']

        if not keyword:
            return query

        q = Q()
        field_search_dict = dict()
        for field in props:
            if field == 'billing_type':
                if keyword.lower() in 'deposit':
                    q = q | Q(billing_type="", credits__gte=0)
                elif keyword.lower() in 'withdraw':
                    q = q | Q(billing_type="", credits__lt=0)
            if field == 'description':
                job_query = JobBillingStatement.objects
                storage_query = StorageBillingStatement.objects
                for filters_dict in param_args['filters']:
                    if filters_dict['prop'] == 'apply_time':
                        job_query = job_query.filter(**{
                            'create_time__range': filters_dict['values'],
                            'bill_group_id': self.bill_group_id
                        })
                        storage_query = storage_query.filter(**{
                            'create_time__range': filters_dict['values'],
                            'bill_group_id': self.bill_group_id
                        })
                        break

                job_ids = job_query.ci_search(
                    **{"scheduler_id": keyword, "job_name": keyword}
                ).values_list('id', flat=True)
                storage_ids = storage_query.ci_search(
                    **{"path": keyword}
                ).values_list('id', flat=True)
                q = q | Q(
                    billing_type='job', billing_id__in=list(job_ids)) | Q(
                    billing_type='storage', billing_id__in=list(storage_ids))
            else:
                field_search_dict.update({field: keyword})

        field_query = query.ci_search(**field_search_dict)
        q_query = query.filter(q)
        return field_query | q_query

    def get_query(self, request, *args, **kwargs):
        set_language(kwargs['language'])
        self.bill_group_id = kwargs['bill_group_id']
        return Deposit.objects.filter(bill_group=kwargs['bill_group_id'])

    def trans_result(self, result):
        ret = result.as_dict(exclude=['bill_group'])
        if ret['billing_type'] == 'job':
            ret['billing'] = JobBillingStatement.objects.get(
                id=ret['billing_id']
            ).as_dict(
                include=['scheduler_id', 'job_id', 'job_name', 'job_end_time'])
        elif ret['billing_type'] == 'storage':
            ret['billing'] = StorageBillingStatement.objects.get(
                id=ret['billing_id']).as_dict(include=['path', 'billing_date'])
        elif ret['billing_type'] == '':
            if ret['credits'] >= 0:
                ret['billing_type'] = 'deposit'
            else:
                ret['billing_type'] = 'withdraw'
        ret['display_type'] = trans_billing_type(ret['billing_type'])
        return ret


class DespositEventLog(EventLog):
    @classmethod
    def action(cls, value):
        return cls.recharge if (float(value) >= 0) else cls.chargeback


class DepositReportView(APIView):
    permission_classes = (AsAdminRole,)

    config = {"billing_group_details": DepositReportExporter}

    @json_schema_validate({
        'type': 'object',
        'properties': {
            'language': {
                'type': 'string',
                'enum': ['sc', 'en']
            },
            'bill_group': {
                'type': 'integer'
            },
            "timezone_offset": {
                "type": "string",
                'pattern': r'^[+-]?\d+$'
            },
            'start_time': {
                'type': 'string',
                'pattern': r'^\d+$'
            },
            'end_time': {
                'type': 'string',
                'pattern': r'^\d+$'
            }
        },
        'required': ['language', 'bill_group', 'start_time', 'end_time']
    })
    def post(self, request, filename):
        param_data = request.data
        language = param_data['language']
        set_language(language)

        try:
            bill_group = BillGroup.objects.get(id=param_data['bill_group'])
        except BillGroup.DoesNotExist:
            raise
        deposit = Deposit.objects.filter(
            bill_group=bill_group).first()

        filename, ext = path.splitext(filename)
        if filename not in self.config or (ext
                                           not in ['.html', '.pdf', '.xlsx']):
            raise InvalidParameterException
        timezone_offset = int(param_data.get('timezone_offset', 0))
        delta = tzoffset('lico/web', -timezone_offset * timedelta(minutes=1))
        start_time = datetime.fromtimestamp(int(param_data['start_time']),
                                            tz=delta)
        create_time = datetime.now(tz=delta)
        if deposit:
            if deposit.billing_type == '':
                start_time = max(deposit.apply_time.astimezone(delta),
                                 start_time)
        report = self.config[filename](
            bill_group=bill_group,
            doctype=ext[1:],
            filename=filename,
            time_delta=delta,
            start_time=start_time,
            end_time=datetime.fromtimestamp(int(param_data['end_time']),
                                            tz=delta),
            creator=request.user.username,
            create_time=create_time,
            template=path.join('report', filename + '.html'),
        )
        stream, ext = report.report_export()
        response = StreamingHttpResponse(stream)
        response['Content-Type'] = 'application/octet-stream'
        response['Content-Disposition'] = (
            f'attachement;filename="'
            f'account_statement_{format_datetime(create_time)}{ext}"')
        return response
