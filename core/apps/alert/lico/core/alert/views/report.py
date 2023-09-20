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

from dateutil.tz import tzoffset
from django.conf import settings
from django.http import StreamingHttpResponse
from django.utils.translation import trans_real
from rest_framework.response import Response

from lico.core.contrib.permissions import AsOperatorRole
from lico.core.contrib.schema import json_schema_validate
from lico.core.contrib.views import APIView

from ..exceptions import InvalidParameterException
from ..utils import (
    _query_alarm_details, _query_alarm_statistics, get_hostnames_from_filter,
)
from .reportbase import ReportExporter

logger = logging.getLogger(__name__)


class AlertReportReview(APIView):
    permission_classes = (AsOperatorRole,)

    def get(self, request):
        format_data = {"total": 0, "data": []}
        start_time = int(request.query_params["start_time"])
        end_time = int(request.query_params["end_time"])
        get_tzinfo = int(request.query_params['timezone_offset'])

        data = {'start_time': start_time, 'end_time': end_time, 'creator': ''}
        datas = _query_alarm_statistics(
            data, tzoffset(
                'lico/web', -get_tzinfo * timedelta(minutes=1)
            )
        )

        format_data['data'] = []
        for data in datas['data']:
            val = {
                "alarm_time": data[0],
                "critical": data[1],
                "error": data[2],
                "warning": data[3],
                "info": data[4],
                "num_total": data[-1]
            }
            format_data['data'].append(val)
            format_data['total'] += val['num_total']

        return Response(format_data)


class AlertReportDownload(APIView):

    permission_classes = (AsOperatorRole,)

    config = {
        'alert_details': (_query_alarm_details, ReportExporter),
        'alert_statistics': (_query_alarm_statistics, ReportExporter),
    }

    I18N = {
        "alert_statistics": {
            "head": [
                "Alert Date",
                "Critical",
                "Error",
                "Warning",
                "Information",
                "Total"
            ],
            "title": "Alert Statistics Report"
        },
        "alert_details": {
            "head": [
                "Alert Time",
                "Alert Name",
                "Alert Source",
                "Alert Level",
                "Alert Status",
                "Remark"
            ],
            "title": "Alert Detailed Report"
        }
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
                "minLength": 1
            },
            "page_direction": {
                "type": "string",
                "enum": ["vertical", "landscape"]
            },
            "node_value_type": {
                'type': 'string',
                'enum': [
                    'hostname', 'rack', 'nodegroup'
                ]
            },
            "node_values": {
                'type': 'string',
                "minLength": 1
            },
            "event_level": {
                'type': 'string',
                'pattern': r'^[0-4]?$'
            }
        },
        "required": [
            "language", "start_time",
            "end_time", "creator", "page_direction"
        ]
    })
    def post(self, request, filename):
        self.set_language(request)
        # set tzinfo
        get_tzinfo = int(request.data.get('timezone_offset', 0))
        target, ext = path.splitext(filename)
        if target not in self.config or ext not in ['.html', '.pdf', '.xlsx']:
            raise InvalidParameterException

        action, exporter = self.config.get(target, (None, ReportExporter))

        context = {
            'headline': self.I18N[target].get('head', None),
            'title': self.I18N[target].get('title', None),
            'subtitle': "",
            'doctype': ext[1:],
            'template': path.join('alert/report', target + '.html'),
            'page_direction': request.data['page_direction'],
            'fixed_offset': tzoffset(
                'lico/web', -get_tzinfo * timedelta(minutes=1)
            ),
            'time_range_flag': False
        }
        node_filter = {
            'value_type': request.data.get(
                'node_value_type', 'hostname'
            ),
            'values': request.data['node_values'].strip(
                ","
            ).split(",") if 'node_values' in request.data else []
        }
        request_data = {
            key: request.data[key] for key in request.data.keys()
        }
        request_data.update(
            node=get_hostnames_from_filter(node_filter)
        )
        context.update(
            action(
                request_data, tzoffset(
                    'lico/web', -get_tzinfo * timedelta(minutes=1)
                )
            )
        )
        stream, ext = exporter(**context).report_export()
        response = StreamingHttpResponse(stream)
        response['Content-Type'] = 'application/octet-stream'
        response['Content-Disposition'] = \
            f'attachement;filename="{uuid.uuid1()}{ext}"'
        return response

    @staticmethod
    def set_language(request):
        set_language = request.data.get('language')
        back_language = dict(settings.LANGUAGES)
        language = set_language if set_language in back_language \
            else settings.LANGUAGE_CODE
        trans_real.activate(language)
