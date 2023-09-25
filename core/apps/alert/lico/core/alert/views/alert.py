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

from django.db.models import Max, Q
from django.db.transaction import atomic
from django.utils.dateparse import parse_datetime
from django.utils.timezone import localtime
from rest_framework.response import Response

from lico.core.contrib.eventlog import EventLog
from lico.core.contrib.permissions import AsOperatorRole
from lico.core.contrib.schema import json_schema_validate
from lico.core.contrib.views import APIView, DataTableView

from ..models import Alert, Policy

logger = logging.getLogger(__name__)


class AlertView(DataTableView):
    permission_classes = (AsOperatorRole,)

    def get_query(self, request, *args, **kwargs):
        return Alert.objects

    def filters_params(self, args, prop, replace_func):
        """
        Use replace_func to replace element in filters[index]['values']
        """
        index = None
        for i, f in enumerate(args['filters']):
            if f['prop'] == prop:
                index = i
                break
        if index:
            args['filters'][index]['values'] = \
                [replace_func(v) for v in args['filters'][index]['values']]
        return args

    def replace_policy_level(self, e):
        values = {
            'fatal': Policy.FATAL,
            'warn': Policy.WARN,
            'error': Policy.ERROR,
            'info': Policy.INFO,
        }
        return values[e]

    def replace_create_time(self, e):
        return parse_datetime(e)

    def params(self, request, args):
        args = self.filters_params(args, 'policy__level',
                                   self.replace_policy_level)
        args = self.filters_params(args, 'create_time',
                                   self.replace_create_time)
        return args

    def global_search(self, query, param_args):  # pragma: no cover
        if 'search' not in param_args or query is None:
            return query
        else:
            search = param_args['search']
            props = search['props']
            keyword = search['keyword']

            q = Q()
            for field in props:
                prop = self.columns_mapping[field] \
                    if field in self.columns_mapping else field
                q |= Q(**{prop + '__icontains': keyword})

            return query.filter(q) if keyword != "" else query

    def trans_result(self, result):

        result_dict = result.as_dict(
            inspect_related=False
        )
        result_dict.update(
            policy__id=result.policy.id,
            policy__name=result.policy.name,
            policy__level=result.policy.get_level_display(),

        )
        result_dict['create_time'] = localtime(result.create_time)
        return result_dict

    @json_schema_validate({
        "type": "object",
        "properties": {
            "filters": {
                "type": "array",
                "properties": {
                    "prop": {"type": "string"},
                    "type": {"type": "string"},
                    "values": {"type": "array"}
                },
                "required": ["prop", "type", "values"]
            },
            "action": {
                "type": "string",
                "enum": ['confirm', 'solve', 'delete']
            }
        },
        "required": ["filters", "action"]
    })
    def patch(self, request):
        params = self.params(request, request.data)

        query = self.get_query(request)
        query = self.filters(query, params['filters'])  # filter

        # add operationlog
        count = query.count()
        EventLog.opt_create(
            request.user.username,
            EventLog.alarm,
            params['action'],
            EventLog.make_list(count, f"{count} records")
        )

        if params['action'] == 'confirm':
            query = query.filter(status__in=['present'])
            query.update(status=Alert.CONFIRMED)
        elif params['action'] == 'solve':
            query.update(status=Alert.RESOLVED)
        elif params['action'] == 'delete':
            query.delete()

        return Response()


class CommentView(APIView):
    permission_classes = (AsOperatorRole,)

    @json_schema_validate({
        "type": "object",
        "properties": {
            "comment": {"type": "string"}
        },
        "required": ["comment"]
    })
    @atomic
    def patch(self, request, pk):
        comment = request.data.get('comment', None)
        alarm = Alert.objects.select_for_update().get(id=pk)
        alarm.comment = comment
        alarm.save()

        # add operationlog
        EventLog.opt_create(
            request.user.username,
            EventLog.alarm,
            EventLog.comment,
            EventLog.make_list(pk, alarm.policy.name)
        )
        return Response()


class NodeAlertView(APIView):
    permission_classes = (AsOperatorRole,)

    def get(self, request, hostname):
        alarm_level = Alert.objects.exclude(status=Alert.RESOLVED)\
            .filter(node=hostname)\
            .aggregate(level=Max('policy__level'))\
            .get('level', Policy.NOTSET)

        return Response(dict(
            node=dict(alarm_level=alarm_level)
        ))


class AlertCountView(APIView):
    permission_classes = (AsOperatorRole,)

    def get(self, request):
        query = Alert.objects.filter(status=Alert.PRESENT)
        return Response({
            'count': query.count()
        })
