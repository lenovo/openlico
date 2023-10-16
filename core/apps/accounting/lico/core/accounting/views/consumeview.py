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
import uuid
from datetime import timedelta
from os import path

from dateutil import tz
from dateutil.parser import parse
from dateutil.tz import tzoffset
from django.db import transaction
from django.db.models import ExpressionWrapper, F, FloatField, Sum
from django.http import StreamingHttpResponse
from pandas import DataFrame
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.status import HTTP_403_FORBIDDEN

from lico.core.accounting.utils import get_local_timezone
from lico.core.contrib.permissions import AsOperatorRole
from lico.core.contrib.schema import json_schema_validate
from lico.core.contrib.views import APIView

from ..exceptions import (
    InvalidParameterException, QueryBillingStatementFailedException,
)
from ..helpers.expense_report_helper import ExpenseReportExporter
from ..models import Gresource, JobBillingStatement, StorageBillingStatement

logger = logging.getLogger(__name__)


def date_string_to_utctime(s_date_str, e_date_str):
    s_date = parse(s_date_str).replace(tzinfo=get_local_timezone())
    e_date = parse(e_date_str).replace(
        tzinfo=get_local_timezone()) + timedelta(days=1)
    s_utcdate = s_date.astimezone(tz=tz.tzutc())
    e_utcdate = e_date.astimezone(tz=tz.tzutc())
    return s_utcdate, e_utcdate


def utctime_to_date_string(utcdate):
    re_date = utcdate.astimezone(tz=get_local_timezone())
    date_string = str(re_date.date())
    return date_string


date_str_pattern = r"^(?:(?!0000)[0-9]{4}([-/.]?)" \
                   r"(?:(?:0?[1-9]|1[0-2])([-/.]?)" \
                   r"(?:0?[1-9]|1[0-9]|2[0-8])|" \
                   r"(?:0?[13-9]|1[0-2])([-/.]?)(?:29|30)" \
                   r"|(?:0?[13578]|1[02])([-/.]?)31)|" \
                   r"(?:[0-9]{2}(?:0[48]|[2468][048]|" \
                   r"[13579][26])|(?:0[48]|[2468][048]|" \
                   r"[13579][26])00)([-/.]?)0?2([-/.]?)29)$"


def filter_by_date_range(start_date, end_date):
    try:
        with transaction.atomic():
            job_bill_query = JobBillingStatement.objects.filter(
                create_time__gte=start_date,
                create_time__lt=end_date
            ).exclude(scheduler_id='')
            storage_bill_query = StorageBillingStatement.objects.filter(
                billing_date__gte=start_date,
                billing_date__lt=end_date
            )
    except Exception:
        logger.exception(
            "Query JobBillingStatement,StorageBillingStatement failed"
        )
        raise QueryBillingStatementFailedException
    return job_bill_query, storage_bill_query


def filter_by_values(value_type, values, job_bill_query, storage_bill_query):
    if not values:
        pass
    elif value_type == 'username':
        job_bill_query = job_bill_query.filter(
            submitter__in=values
        )
        storage_bill_query = storage_bill_query.filter(
            username__in=values
        )
    else:
        job_bill_query = job_bill_query.filter(
            bill_group_id__in=values
        )
        storage_bill_query = storage_bill_query.filter(
            bill_group_id__in=values
        )

    return job_bill_query, storage_bill_query


class CostStatisticView(APIView):
    @staticmethod
    def daily_consume_statistic(
            job_bill_daily_query, storage_bill_daily_query
    ):
        storage_bill_queryset = storage_bill_daily_query. \
            values('path'). \
            annotate(cost=Sum('billing_cost')).values('path', 'cost')
        job_bill_queryset = job_bill_daily_query.values('queue'). \
            annotate(
            cpu_costs=ExpressionWrapper(
                Sum(F('cpu_cost') * F('discount')),
                output_field=FloatField()
            ),
            mem_costs=ExpressionWrapper(
                Sum(F('memory_cost') * F('discount')),
                output_field=FloatField())
        ).values('queue', 'cpu_costs', 'mem_costs')

        storage_bill_list = list(storage_bill_queryset)
        job_bill_list = list(job_bill_queryset)

        return job_bill_list, storage_bill_list

    @staticmethod
    def get_gres_costs(gres_cost_list, queue_name):
        gresources = Gresource.objects.filter(billing=True)
        if not gresources.exists():
            return dict()
        gres_codes = [gres.code for gres in gresources]
        gres_costs = {gres: list() for gres in gres_codes}

        for queue, gres_cost, discount in gres_cost_list:
            if queue_name == queue:
                # gres_cost = json.loads(gres_cost)
                for gres in gres_codes:
                    gres_item_cost = gres_cost[gres] \
                        if gres in gres_cost else 0
                    gres_item_cost *= float(discount)
                    gres_costs[gres].append(gres_item_cost)

        for gres in gres_codes:
            gres_costs[gres] = round(sum(gres_costs[gres]), 2)
        return gres_costs

    @staticmethod
    def filter_by_day(day_start, day_end, job_queryset, storage_queryset):
        job_queryset = job_queryset.filter(
            create_time__gte=day_start,
            create_time__lt=day_end
        )
        storage_queryset = storage_queryset.filter(
            billing_date__gte=day_start,
            billing_date__lt=day_end
        )

        return job_queryset, storage_queryset

    @json_schema_validate({
        "type": "object",
        "required": ["args"],
        "properties": {
            "role": {
                "type": "string",
                "const": "admin",
            },
            "args": {
                "type": "object",
                "required": ["start_date", "end_date"],
                "properties": {
                    "start_date": {
                        "type": "string",
                        "pattern": date_str_pattern
                    },
                    "end_date": {
                        "type": "string",
                        "pattern": date_str_pattern
                    },
                    "filter": {
                        "type": "object",
                        "required": ["values", "value_type"],
                        "properties": {
                            "value_type": {
                                "type": "string",
                                "enum": ["username", "billinggroup"]
                            },
                            "values": {
                                "type": "array",
                                "minItems": 0,
                                "uniqueItems": True,
                            }
                        }
                    }
                }
            },
        }
    })
    def post(self, request):
        username = request.user.username
        args = request.data['args']
        role = request.data.get('role', None)
        data_list = []

        start_date, end_date = date_string_to_utctime(
            args['start_date'], args['end_date']
        )
        job_bill_query, storage_bill_query = filter_by_date_range(
            start_date, end_date
        )

        if role:
            if request.user.role < AsOperatorRole.floor:
                logger.exception('User role has no permission'
                                 'for get other user billing reports')
                return Response(status=HTTP_403_FORBIDDEN)

            value_type = args['filter']['value_type']
            values = args['filter']['values']
            job_bill_query, storage_bill_query = filter_by_values(
                value_type, values, job_bill_query, storage_bill_query
            )
        else:
            job_bill_query = job_bill_query.filter(submitter=username)
            storage_bill_query = storage_bill_query.filter(
                username=username
            )

        if not job_bill_query.exists() and not storage_bill_query.exists():
            return Response(data_list)

        date_range = (end_date - start_date).days
        for i in range(date_range):
            day_start = start_date + timedelta(days=i)
            day_end = day_start + timedelta(days=1)

            job_bill_daily_query, storage_bill_daily_query = \
                self.filter_by_day(
                    day_start, day_end, job_bill_query, storage_bill_query
                )
            job_bill_list, storage_bill_list = self.daily_consume_statistic(
                job_bill_daily_query, storage_bill_daily_query
            )

            gres_cost_list = list(job_bill_daily_query.values_list(
                'queue', 'gres_cost', 'discount'
            ))

            for q in job_bill_list:
                q.update(self.get_gres_costs(gres_cost_list, q['queue']))

            start_date_string = utctime_to_date_string(day_start)
            data_list.append({
                'date': start_date_string,
                'cost': {'queue': job_bill_list, 'storage': storage_bill_list}
            })

        return Response(data_list)


class ConsumeRankingView(APIView):
    permission_classes = (AsOperatorRole,)

    @staticmethod
    def union_job_storage_bill_list(job_bill_query, storage_bill_query):
        union_query = job_bill_query.values('submitter').annotate(
            user_name=F('submitter'),
            costs=Sum('billing_cost')
        ).values_list(
            'user_name',
            'costs'
        ).union(storage_bill_query.values('username').annotate(
            user_name=F('username'),
            costs=Sum('billing_cost')
        ).values_list('user_name', 'costs'), all=True)

        return list(union_query)

    @staticmethod
    def consume_aggregate(union_list):
        """
        :param union_list:[
        ('user1', 2), ('user1', 5), ('user2', 4), ('user3', 10)...
        ]
        :return:[['user3', 10], ['user1', 7], ['user2', 4]...]
        """
        t_list = DataFrame(union_list).groupby(0).sum().to_records()
        rank_list = [list(i) for i in t_list]
        rank_list.sort(key=lambda x: (x[1], x[0]), reverse=True)

        return rank_list

    @json_schema_validate({
        "type": "object",
        "required": ["args"],
        "properties": {
            "args": {
                "type": "object",
                "required": ["start_date", "end_date", "filter"],
                "properties": {
                    "start_date": {
                        "type": "string",
                        "pattern": date_str_pattern
                    },
                    "end_date": {
                        "type": "string",
                        "pattern": date_str_pattern
                    },
                    "filter": {
                        "type": "object",
                        "required": ["values", "value_type"],
                        "properties": {
                            "value_type": {
                                "type": "string",
                                "enum": ["username", "billinggroup"]
                            },
                            "values": {
                                "type": "array",
                                "minItems": 0,
                                "uniqueItems": True,
                            }
                        }
                    }
                }
            },
        }}
    )
    def post(self, request):
        dataparams = request.data
        args = dataparams['args']
        start_date, end_date = date_string_to_utctime(
            args['start_date'], args['end_date']
        )
        value_type = args['filter']['value_type']
        values = args['filter']['values']
        job_bill_query, storage_bill_query = filter_by_date_range(
            start_date, end_date
        )
        job_bill_query, storage_bill_query = filter_by_values(
            value_type, values, job_bill_query, storage_bill_query
        )

        if not job_bill_query.exists() and not storage_bill_query.exists():
            return Response({})

        union_list = self.union_job_storage_bill_list(
            job_bill_query, storage_bill_query
        )
        rank_list = self.consume_aggregate(union_list)

        data = {
            'total': len(rank_list[:10:]),
            'data': rank_list[:10:]
        }
        return Response(data)


class ExpenseReportView(APIView):

    config = {"expense_details": ExpenseReportExporter}

    @json_schema_validate({
        "type": "object",
        "required": ["args", "timezone_offset"],
        "properties": {
            "timezone_offset": {
                "type": "string",
                'pattern': r'^[+-]?\d+$'
            },
            "role": {
                "type": "string",
                "const": "admin",
            },
            "args": {
                "type": "object",
                "required": ["start_date", "end_date"],
                "properties": {
                    "start_date": {
                        "type": "string",
                        "pattern": date_str_pattern
                    },
                    "end_date": {
                        "type": "string",
                        "pattern": date_str_pattern
                    },
                    "filter": {
                        "type": "object",
                        "required": ["values", "value_type"],
                        "properties": {
                            "value_type": {
                                "type": "string",
                                "enum": ["username", "billinggroup"]
                            },
                            "values": {
                                "type": "array",
                                "minItems": 0,
                                "uniqueItems": True,
                            }
                        }
                    }
                }
            },
        }
    })
    def post(self, request, filename):
        username = request.user.username
        args = request.data['args']
        role = request.data.get('role', None)
        get_tzinfo = int(request.data.get('timezone_offset', 0))
        filename, ext = path.splitext(filename)
        if filename not in self.config or ext not in ['.csv']:
            raise InvalidParameterException
        start_date, end_date = date_string_to_utctime(
            args['start_date'], args['end_date']
        )
        job_bill_query, storage_bill_query = filter_by_date_range(
            start_date, end_date
        )
        if role:
            if request.user.role < AsOperatorRole.floor:
                logger.exception('User role has no permission'
                                 'for get other user billing reports')
                raise PermissionDenied

            value_type = args['filter']['value_type']
            values = args['filter']['values']
            job_bill_query, storage_bill_query = filter_by_values(
                value_type, values, job_bill_query, storage_bill_query
            )
        else:
            job_bill_query = job_bill_query.filter(submitter=username)
        report = self.config[filename](
            bill_query=job_bill_query,
            doctype=ext[1:],
            timezone_offset=tzoffset(
                'lico/web', -get_tzinfo * timedelta(minutes=1)
            )
        )
        stream, ext = report.report_export()
        filename = str(uuid.uuid1())
        response = StreamingHttpResponse(stream)
        response['Content-Type'] = 'application/octet-stream'
        response['Content-Disposition'] = \
            f'attachement;filename="{filename}{ext}"'
        return response
