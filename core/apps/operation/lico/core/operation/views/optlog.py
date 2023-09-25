# -*- coding:utf-8 -*-
# Copyright 2020-present Lenovo
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

import datetime
import logging
from collections import namedtuple
from datetime import timedelta
from functools import reduce

from dateutil.tz import tzoffset, tzutc
from django.conf import settings
from django.http import StreamingHttpResponse
from django.utils.dateparse import parse_datetime
from django.utils.timezone import localtime
from django.utils.translation import trans_real, ugettext as _

from lico.core.contrib.client import Client
from lico.core.contrib.permissions import AsOperatorRole
from lico.core.contrib.schema import json_schema_validate
from lico.core.contrib.views import APIView, DataTableView

from ..models import LogDetail, OperationLog
from .logbase import LogExporter

logger = logging.getLogger(__name__)


class OptLogView(DataTableView):
    columns_mapping = {
        'id': 'id',
        'operator': 'operator',
        'module': 'module',
        'operation': 'operation',
        'operate_time': 'operate_time',
        'target': 'target'
    }

    def trans_result(self, result):
        return {
            'id': result.id,
            'operator': result.operator,
            'module': result.module,
            'operation': result.operation,
            'operate_time': localtime(result.operate_time),
            'target': LogDetail.objects.filter(optlog=result.id).values('name')
        }

    def get_query(self, request, *args, **kwargs):
        return OperationLog.objects

    def get_users_from_filter(self, filter):  # pragma: no cover
        value_type = filter['value_type']
        values = filter['values']
        # Handle "all"
        if len(values) <= 0:
            return []
        if value_type.lower() == 'username':
            return values
        elif value_type.lower() == 'usergroup':
            usernames = []
            for value in values:
                usernames.extend(
                    Client().user_client().get_group_user_list(value))
            if len(usernames) == 0 and len(values) > 0:
                return ['LICO-NOT-EXIST-USERNAME']
            return usernames
        elif value_type.lower() == 'billinggroup':
            """
            users_list format:
            [
                BillGroupUserList(
                    bill_group_id=1,
                    username_list=['hpcuser1', 'user6', 'hpcuser2',]
                    ),
                BillGroupUserList(
                    bill_group_id=2,
                    username_list=[])
                    )
            ]
            """
            users_list = Client().accounting_client().get_username_list(values)
            usernames = reduce(
                lambda x, y: x + y,
                [
                    user_obj.username_list for user_obj in users_list
                ] if users_list else [[]]
            )
            if len(usernames) == 0 and len(values) > 0:
                return ['LICO-NOT-EXIST-USERNAME']
            return usernames
        return None

    def filters(self, query, filters):
        for field in filters:
            values = []
            if field['prop'] == 'operate_time':
                for times in field['values']:
                    values.append(parse_datetime(times))
                field['values'] = values
            # Handler 'operator' filter to compatible with following code
            if field['prop'] == 'operator':
                field['values'] = self.get_users_from_filter(field)
                field['value_type'] = 'username'
        return super(OptLogView, self).filters(query, filters)


class OptDownloadView(APIView):
    permission_classes = (AsOperatorRole,)

    @json_schema_validate({
        "type": "object",
        "properties": {
            "timezone_offset": {
                "type": "string"
            },
            "language": {
                "type": "string"
            },
            "start_time": {
                "type": "string",
            },
            "end_time": {
                "type": "string",
            },
            "creator": {
                "type": "string",
            },
            "page_direction": {
                "type": "string",
                "enum": ["vertical", "landscape"]
            },
            "format": {
                "type": "string",
            }
        },
        "required": [
            "language",
            "start_time",
            "end_time",
            "creator",
            "page_direction",
            "format"
        ]
    })
    def post(self, request):
        data = request.data
        self.set_language(data)
        # set tzinfo
        get_tzinfo = int(data.get('timezone_offset', 0))
        context = {
            'headline': [
                "operation.Time", "operation.Module", "operation.Operator",
                "operation.Operation", "operation.Operating Details"
            ],
            'title': "operation.Operation Log Detailed Report",
            'subtitle': "",
            'doctype': data['format'],
            'template': 'log/operation_details.html',
            'page_direction': data['page_direction'],
            'fixed_offset': tzoffset(
                'lico/web', -get_tzinfo * timedelta(minutes=1)
            ),
            'time_range_flag': False
        }
        try:
            context.update(
                self._query_operation_details(
                    data, tzoffset(
                        'lico/web', -get_tzinfo * timedelta(minutes=1)
                    )
                )
            )
        except Exception:
            logger.exception(
                "Generate operation_details log failed")
            raise
        stream, ext = LogExporter(**context).report_export()
        response = StreamingHttpResponse(stream)
        response['Content-Type'] = 'application/octet-stream'
        response['Content-Disposition'] = \
            f'attachement;filename="{ext}"'

        return response

    def set_language(self, data):
        set_language = data.get('language', False)
        back_language = dict(settings.LANGUAGES)
        if set_language in back_language:
            language = set_language
        else:
            language = settings.LANGUAGE_CODE
        trans_real.activate(language)

    @staticmethod
    def _get_datetime(data):
        start_time = datetime.datetime.fromtimestamp(
            int(data["start_time"]), tz=tzutc())
        end_time = datetime.datetime.fromtimestamp(
            int(data["end_time"]), tz=tzutc())
        return start_time, end_time

    @staticmethod
    def _get_create_info(data):
        return data["creator"], datetime.datetime.now(tz=tzutc())

    @staticmethod
    def _translate_operation_data(instances_list, fixed_offset):
        def _get_operationlog_target(target):
            return ','.join(
                [item_target.name for item_target in target if len(target)]
            )

        return [(
            '{0:%Y-%m-%d %H:%M:%S}'.format(
                item.operate_time.astimezone(fixed_offset)
            ),
            _('operation.' + item.module),
            item.operator,
            _('operation.' + item.operation),
            ' '.join([
                item.operator,
                _('operation.' + item.operation),
                _('operation.' + item.module),
                _get_operationlog_target(item.target.all())
            ])
        ) for item in instances_list if len(instances_list)]

    def _query_operation_details(self, data, fixed_offset):
        start_time, end_time = self._get_datetime(data)
        creator, create_time = self._get_create_info(data)
        objs = OperationLog.objects.filter(
            operate_time__gte=start_time,
            operate_time__lte=end_time
        )
        values = self._translate_operation_data(objs, fixed_offset)
        context_tuple = namedtuple(
            "context", ['data', 'start_time', 'end_time',
                        'creator', 'create_time', 'operator'])
        return context_tuple(
            values,
            start_time.astimezone(fixed_offset),
            end_time.astimezone(fixed_offset),
            creator,
            create_time.astimezone(fixed_offset),
            settings.LICO.ARCH
        )._asdict()
