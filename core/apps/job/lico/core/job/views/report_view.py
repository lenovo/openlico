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

import copy
import json
import logging
import uuid
from collections import defaultdict, namedtuple
from datetime import datetime, timedelta
from os import path
from typing import Any

from dateutil.tz import tzoffset, tzutc
from django.conf import settings
from django.http import StreamingHttpResponse
from django.utils.translation import trans_real
from pandas import DataFrame
from rest_framework.response import Response

from lico.core.contrib.permissions import AsOperatorRole
from lico.core.contrib.schema import json_schema_validate
from lico.core.contrib.views import APIView
from lico.core.job.models import Job
from lico.core.job.utils import (
    get_bg_names_from_data, get_resource_num, get_user_bill_group_mapping,
    get_users_from_bill_ids, get_users_from_filter,
)

from ..etc import I18N
from ..exceptions import InvalidParameterException
from .reportbase import GroupReportExporter, ReportExporter

logger = logging.getLogger(__name__)
context_tuple = namedtuple(
    "context", ['data', 'start_time', 'end_time',
                'creator', 'create_time', 'operator'])


def _get_datetime(data):
    return datetime.fromtimestamp(int(data["start_time"]), tz=tzutc()), \
           datetime.fromtimestamp(int(data["end_time"]), tz=tzutc())


def _get_create_info(data):
    return data["creator"], datetime.now(tz=tzutc())


def _get_head_title(target):
    return I18N[target]['title'], I18N[target]['head']


def _convert_tres_value(tres, runtime):
    if not tres:
        return [0, 0, 0, 0]
    runtime = 0 if runtime < 0 else runtime
    cpu_num, gpu_num = 0, 0
    for tres_detail in tres.split(','):
        res_type, value = tres_detail.split(':')
        if res_type == 'C':
            cpu_num = int(float(value))
            continue
        type_list = res_type.split('/')
        if type_list[0] == 'G':
            gpu_num = int(float(value))
            continue
    return [cpu_num, cpu_num * runtime, gpu_num, gpu_num * runtime]


def _query_jobs_info(data, order_by=False):
    start_time, end_time = _get_datetime(data)
    creator, create_time = _get_create_info(data)
    query = Job.objects.exclude(scheduler_id="", end_time=None)
    if order_by:
        query = query.order_by("submit_time", "id")
    if data.get('bg_users') is None:
        users = data['users']
    else:
        users = set(data['bg_users'])
    if users:
        query = query.filter(submitter__in=users)
    query = query.filter(
        submit_time__gte=start_time, submit_time__lte=end_time, state="C"
    )
    return query.as_dict(include=data.get("fields", [])), \
        start_time, end_time, creator, create_time


def _query_jobs_details(data, fixed_offset):
    data["fields"] = [
        "scheduler_id", "job_name", "state",
        "queue", "submit_time", "start_time",
        "end_time", "submitter", "runtime", "tres"]
    tmp_values, start_time, end_time, creator, create_time = \
        _query_jobs_info(data, order_by=True)
    # This is a example for tmp_values
    # tmp_values = [
    # {u'submitter': u'k8s_user_04', u'state': u'C', u'job_name': u'test1'},
    # {},
    # ........]
    need_convert = ["submit_time", "start_time", "end_time"]
    values = []
    for tmp_value in tmp_values:
        job_status = tmp_value['state']
        need_exclude = []
        if job_status.lower() == 'q':
            need_exclude.extend(["start_time", "end_time"])
        elif job_status.lower() != 'c' and job_status.lower() != 'cancelled':
            need_exclude.append("end_time")

        for value in need_convert:
            if value in need_exclude:
                tmp_value[value] = ""
                continue
            tmp_value[value] = '{0:%Y-%m-%d %H:%M:%S}'.format(
                datetime.fromtimestamp(tmp_value[value], tz=fixed_offset)
            ) if (tmp_value[value] and tmp_value[value] != 0) else ""
        tres_value = _convert_tres_value(
            tmp_value['tres'], tmp_value['runtime']
        )
        values.append(
            [tmp_value.get(k) for k in data["fields"][:-2]] + tres_value
        )
    return context_tuple(
        values,
        start_time.astimezone(fixed_offset),
        end_time.astimezone(fixed_offset),
        creator,
        create_time.astimezone(fixed_offset),
        settings.LICO.ARCH
    )._asdict()


def _query_jobs_statistics(data, fixed_offset):
    start_time, end_time = _get_datetime(data)
    creator, create_time = _get_create_info(data)
    context_data = [
        [],
        start_time.astimezone(fixed_offset),
        end_time.astimezone(fixed_offset),
        creator,
        create_time.astimezone(fixed_offset),
        settings.LICO.ARCH
    ]
    query = Job.objects.exclude(scheduler_id="", end_time=None)
    if data['users']:
        query = query.filter(submitter__in=data['users'])
    query_data = query.filter(
        submit_time__gte=start_time, submit_time__lte=end_time, state="C"
    ).as_dict(
        include=['submit_time', 'runtime', 'tres']
    )
    if not query_data:
        return context_tuple(*context_data)._asdict()
    df = DataFrame(query_data)
    fixed_offset_seconds = int(fixed_offset.utcoffset(0).total_seconds())
    df['date'] = (df['submit_time'] + fixed_offset_seconds) // 86400 * 86400
    df['runtime'] = df['runtime'].apply(lambda x: 0 if x < 0 else x)
    for gres_code in ['cpu_cores', 'gpu']:
        df[gres_code] = df['tres'].apply(get_resource_num, args=(gres_code,))
    values = []
    for date, tmp_value in df.groupby('date'):
        value = [Any] * 6
        value[0] = '{0:%Y-%m-%d}'.format(
            datetime.fromtimestamp(date, tz=fixed_offset))
        value[1] = len(tmp_value)
        value[2] = tmp_value["cpu_cores"].sum()
        value[3] = (tmp_value["cpu_cores"] *
                    tmp_value["runtime"]).sum()
        value[4] = tmp_value["gpu"].sum()
        value[5] = (tmp_value["gpu"] *
                    tmp_value["runtime"]).sum()
        values.append(value)

    context_data[0] = values
    return context_tuple(*context_data)._asdict()


def _query_user_details(data, fixed_offset):
    data["fields"] = [
        "scheduler_id", "job_name", "state",
        "queue", "submit_time", "start_time",
        "end_time", "submitter", "runtime", "tres"]
    tmp_values, start_time, end_time, creator, create_time = \
        _query_jobs_info(data, order_by=True)
    need_convert = ["submit_time", "start_time", "end_time"]

    group_data = defaultdict(list)
    for tmp_value in tmp_values:
        user = tmp_value["submitter"]
        job_status = tmp_value["state"]
        need_exclude = []
        if job_status.lower() == 'q':
            need_exclude.extend(["start_time", "end_time"])
        elif job_status.lower() != 'c' \
                and job_status.lower() != 'cancelled':
            need_exclude.append("end_time")

        for value in need_convert:
            if value in need_exclude:
                tmp_value[value] = ""
                continue
            tmp_value[value] = '{0:%Y-%m-%d %H:%M:%S}'.format(
                datetime.fromtimestamp(tmp_value[value], tz=fixed_offset)
            ) if (tmp_value[value] and tmp_value[value] != 0) else ""

        tres_value = _convert_tres_value(
            tmp_value['tres'], tmp_value['runtime']
        )
        group_data[user].append(
            [tmp_value.get(k) for k in data["fields"][:-2]] + tres_value
        )

    return context_tuple(
        list(group_data.items()),
        start_time.astimezone(fixed_offset),
        end_time.astimezone(fixed_offset),
        creator,
        create_time.astimezone(fixed_offset),
        settings.LICO.ARCH
    )._asdict()


def _query_user_statistics(data, fixed_offset):
    start_time, end_time = _get_datetime(data)
    creator, create_time = _get_create_info(data)
    context_data = [
        [],
        start_time.astimezone(fixed_offset),
        end_time.astimezone(fixed_offset),
        creator,
        create_time.astimezone(fixed_offset),
        settings.LICO.ARCH
    ]
    query = Job.objects.exclude(scheduler_id="", end_time=None)
    if data['users']:
        query = query.filter(submitter__in=data['users'])
    query_data = query.filter(
        submit_time__gte=start_time, submit_time__lte=end_time, state="C"
    ).as_dict(
        include=['submitter', 'submit_time', 'runtime', 'tres']
    )
    if not query_data:
        return context_tuple(*context_data)._asdict()
    df = DataFrame(query_data)
    fixed_offset_seconds = int(fixed_offset.utcoffset(0).total_seconds())
    df['date'] = (df['submit_time'] + fixed_offset_seconds) // 86400 * 86400
    df['runtime'] = df['runtime'].apply(lambda x: 0 if x < 0 else x)

    for gres_code in ['cpu_cores', 'gpu']:
        df[gres_code] = df['tres'].apply(get_resource_num, args=(gres_code,))

    group_data = defaultdict(list)
    for date, date_value in df.groupby('date'):
        for user, tmp_value in date_value.groupby('submitter'):
            # if user in group_data:
            value = [Any] * 7
            value[0] = '{0:%Y-%m-%d}'.format(
                datetime.fromtimestamp(date, tz=fixed_offset)
            )
            value[1] = user
            value[2] = len(tmp_value)
            value[3] = tmp_value["cpu_cores"].sum()
            value[4] = (tmp_value["cpu_cores"] *
                        tmp_value["runtime"]).sum()
            value[5] = tmp_value["gpu"].sum()
            value[6] = (tmp_value["gpu"] *
                        tmp_value["runtime"]).sum()
            group_data[user].append(value)

    context_data[0] = list(group_data.items())
    return context_tuple(*context_data)._asdict()


def _query_bill_details(data, fixed_offset):
    data["fields"] = [
        "scheduler_id", "job_name", "state",
        "queue", "submit_time", "start_time",
        "end_time", "submitter", "runtime", "tres"]
    tmp_values, start_time, end_time, creator, create_time = \
        _query_jobs_info(data, order_by=True)
    need_convert = ["submit_time", "start_time", "end_time"]
    user_bg_mapping = get_user_bill_group_mapping()
    group_data = defaultdict(list)
    for tmp_value in tmp_values:
        bg_name = user_bg_mapping.get(tmp_value["submitter"], '-')
        job_status = tmp_value["state"]
        need_exclude = []
        if job_status.lower() == 'q':
            need_exclude.extend(["start_time", "end_time"])
        elif job_status.lower() != 'c' \
                and job_status.lower() != 'cancelled':
            need_exclude.append("end_time")

        for value in need_convert:
            if value in need_exclude:
                tmp_value[value] = ""
                continue
            tmp_value[value] = '{0:%Y-%m-%d %H:%M:%S}'.format(
                datetime.fromtimestamp(
                    tmp_value[value], tz=fixed_offset)
            ) if (tmp_value[value] and tmp_value[value] != 0) else ""
        tres_value = _convert_tres_value(
            tmp_value['tres'], tmp_value['runtime']
        )
        group_data[bg_name].append(
            [tmp_value.get(k) for k in data["fields"][:-2]] + tres_value
        )

    return context_tuple(
        list(group_data.items()),
        start_time.astimezone(fixed_offset),
        end_time.astimezone(fixed_offset),
        creator,
        create_time.astimezone(fixed_offset),
        settings.LICO.ARCH
    )._asdict()


def _query_bill_statistics(data, fixed_offset):
    start_time, end_time = _get_datetime(data)
    creator, create_time = _get_create_info(data)
    context_data = [
        [],
        start_time.astimezone(fixed_offset),
        end_time.astimezone(fixed_offset),
        creator,
        create_time.astimezone(fixed_offset),
        settings.LICO.ARCH
    ]
    query = Job.objects.exclude(scheduler_id="", end_time=None)
    users = set(data['bg_users'])
    query = query.filter(submitter__in=users) if users else query
    query_data = query.filter(
        submit_time__gte=start_time, submit_time__lte=end_time, state="C"
    ).as_dict(
        include=['submitter', 'submit_time', 'runtime', 'tres']
    )
    if not query_data:
        return context_tuple(*context_data)._asdict()

    df = DataFrame(query_data)
    user_bg_mapping = get_user_bill_group_mapping()
    fixed_offset_seconds = int(fixed_offset.utcoffset(0).total_seconds())
    df['date'] = (df['submit_time'] + fixed_offset_seconds) // 86400 * 86400
    df['bill_group'] = \
        df['submitter'].apply(lambda user: user_bg_mapping.get(user, '-'))
    df['runtime'] = df['runtime'].apply(lambda x: 0 if x < 0 else x)

    for gres_code in ['cpu_cores', 'gpu']:
        df[gres_code] = df['tres'].apply(get_resource_num, args=(gres_code,))
    group_data = defaultdict(list)
    for date, date_value in df.groupby('date'):
        for bg_name, tmp_value in date_value.groupby('bill_group'):
            value = [Any] * 7
            value[0] = '{0:%Y-%m-%d}'.format(
                datetime.fromtimestamp(date, tz=fixed_offset))
            value[1] = bg_name
            value[2] = len(tmp_value)
            value[3] = tmp_value["cpu_cores"].sum()
            value[4] = (tmp_value["cpu_cores"] *
                        tmp_value["runtime"]).sum()
            value[5] = tmp_value["gpu"].sum()
            value[6] = (tmp_value["gpu"] *
                        tmp_value["runtime"]).sum()
            group_data[bg_name].append(value)

    context_data[0] = list(group_data.items())
    return context_tuple(*context_data)._asdict()


class ReportView(APIView):
    permission_classes = (AsOperatorRole,)

    config = {
        'jobs_details': (_query_jobs_details, ReportExporter),
        'jobs_statistics': (_query_jobs_statistics, ReportExporter),
        'user_details': (_query_user_details, GroupReportExporter),
        'user_statistics': (_query_user_statistics, GroupReportExporter),
        'bill_details': (_query_bill_details, GroupReportExporter),
        'bill_statistics': (_query_bill_statistics, GroupReportExporter),
    }

    @json_schema_validate({
        "type": "object",
        "properties": {
            "timezone_offset": {
                "type": "string",
                'pattern': r'^[+-]?\d+$'
            },
            "language": {
                "type": "string"
            },
            "start_time": {
                "type": "string",
                'pattern': r'^\d+$'
            },
            "end_time": {
                "type": "string",
                'pattern': r'^\d+$'
            },
            "creator": {
                "type": "string",
                "minLength": 1,
            },
            "page_direction": {
                "type": "string",
                "enum": ["vertical", "landscape"]
            },
            "url": {
                "type": "string",
                "minLength": 1,
            },
            "bill": {
                "type": "string"
            },
            "job_user": {
                "type": "string"
            },
        },
        "required": [
            "language",
            "start_time",
            "end_time",
            "creator",
            "page_direction"]
    })
    def post(self, request, filename):
        self.set_language(request)
        # set tzinfo
        request_data = copy.deepcopy(request.data)
        get_tzinfo = int(request_data.get('timezone_offset', 0))
        target, ext = path.splitext(filename)
        if target not in self.config or ext not in ['.html', '.pdf', '.xlsx']:
            raise InvalidParameterException

        action, exporter = self.config.get(target, (None, ReportExporter))
        context = {
            'headline': I18N[target].get('head', None),
            'title': I18N[target].get('title', None),
            'subtitle': "",
            'doctype': ext[1:],
            'template': path.join('report', target + '.html'),
            'page_direction': request.data['page_direction'],
            'fixed_offset': tzoffset(
                'lico/web', -get_tzinfo * timedelta(minutes=1)
            )
        }
        request_data["users"] = get_users_from_filter(
            json.loads(request.data["job_user"]), ignore_non_lico_user=False)
        if target.startswith('bill'):
            bill = json.loads(request.data["bill"])
            request_data["bg_names"] = get_bg_names_from_data(bill)
            request_data["bg_users"] = get_users_from_bill_ids(bill)
        try:
            context.update(
                action(
                    request_data, tzoffset(
                        'lico/web', -get_tzinfo * timedelta(minutes=1)
                    )
                )
            )
        except Exception:
            logger.exception(
                "Generate {0} {1} report failed".format(target, ext))
            raise

        stream, ext = exporter(**context).report_export()
        filename = str(uuid.uuid1())
        response = StreamingHttpResponse(stream)
        response['Content-Type'] = 'application/octet-stream'
        response['Content-Disposition'] = \
            f'attachement;filename="{filename}{ext}"'
        return response

    def set_language(self, request):
        set_language = request.data.get('language')
        back_language = dict(settings.LANGUAGES)
        if set_language in back_language:
            language = set_language
        else:
            language = settings.LANGUAGE_CODE
        trans_real.activate(language)


class JobReportPreview(APIView):
    permission_classes = (AsOperatorRole,)

    @json_schema_validate({
        "type": "object",
        "properties": {
            "start_time": {
                "type": "string",
                'pattern': r'^\d+$'
            },
            "end_time": {
                "type": "string",
                'pattern': r'^\d+$'
            },
            "filters": {
                "anyof": [
                    {
                        "type": "object",
                        "properties": {
                            "values": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                }
                            },
                            "value_type": {"type": "string"},
                        },
                    },
                    {
                        "type": "array",
                    }
                ],
            },
            "timezone_offset": {
                "type": "string",
                'pattern': r'^[+-]?\d+$'
            },
        },
        "required": [
            "start_time",
            "end_time",
            "filters",
            "timezone_offset"]
    })
    def post(self, request, category):
        format_data = {"total": 0, "data": []}
        category_mapping = {'user': 'user', 'job': 'job',
                            'bill_group': 'bill_group'}
        start_time, end_time = _get_datetime(request.data)
        filters = request.data["filters"]
        get_tzinfo = int(request.data['timezone_offset'])
        if category not in category_mapping:
            return format_data
        category = category_mapping[category]
        if category == 'bill_group':
            users = get_users_from_bill_ids(filters)
        else:
            users = get_users_from_filter(filters, ignore_non_lico_user=False)

        query = Job.objects.exclude(scheduler_id="", end_time=None)
        if users:
            query = query.filter(submitter__in=users)
        query_data = query.filter(
            submit_time__gte=start_time, submit_time__lte=end_time, state="C"
        ).as_dict(
            include=['runtime', 'submit_time', 'submitter', 'tres']
        )
        if not query_data:
            return Response({'total': 0, 'data': []})
        df = DataFrame(query_data)
        user_bg_mapping = get_user_bill_group_mapping()
        df['date'] = (df['submit_time'] - get_tzinfo * 60) // 86400 * 86400
        df['runtime'] = df['runtime'].apply(lambda x: 0 if x < 0 else x)

        for gres_code in ['cpu_cores', 'gpu']:
            df[gres_code] = df['tres'].apply(
                get_resource_num, args=(gres_code,))

        format_data['data'] = []
        grouped_data = df.groupby('date')
        for date, value in grouped_data:
            for submitter, tmp_value in value.groupby('submitter'):
                values = {}
                if category != 'job':
                    values['name'] = submitter if category == 'user' \
                        else user_bg_mapping.get(submitter, '-')
                values['start_time'] = '{0:%Y-%m-%d}'.format(
                    datetime.fromtimestamp(
                        date,
                        tz=tzoffset(
                            'lico/web', -get_tzinfo * timedelta(minutes=1)
                        )
                    )
                )
                values['job_count'] = len(tmp_value)
                values['cpu_count'] = tmp_value["cpu_cores"].sum()
                values['cpu_runtime'] = (tmp_value["cpu_cores"] *
                                         tmp_value["runtime"]).sum()
                values['gpu_count'] = tmp_value["gpu"].sum()
                values['gpu_runtime'] = (tmp_value["gpu"] *
                                         tmp_value["runtime"]).sum()
                format_data['data'].append(values)
        format_data['total'] = len(grouped_data)
        return Response(format_data)
