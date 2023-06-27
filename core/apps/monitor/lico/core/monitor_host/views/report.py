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
from collections import defaultdict
from datetime import datetime, timedelta
from os import path

from dateutil.tz import tzoffset, tzutc
from django.conf import settings
from django.http import StreamingHttpResponse
from django.utils.translation import trans_real
from influxdb.exceptions import InfluxDBClientError, InfluxDBServerError
from rest_framework.response import Response

from lico.core.contrib.permissions import AsOperatorRole
from lico.core.contrib.schema import json_schema_validate
from lico.core.contrib.views import APIView
from lico.core.monitor_host.views.reportbase import GroupReportExporter

from ..exceptions import (
    ExportReportException, InfluxDBException, InvalidParamException,
)
from ..utils import ClusterClient, InfluxClient

logger = logging.getLogger(__name__)


def _get_datetime(data):
    return (
        datetime.fromtimestamp(int(data.get("start_time", 0)), tz=tzutc()),
        datetime.fromtimestamp(int(data.get("end_time", 0)), tz=tzutc())
    )


def _get_create_info(data):
    return data["creator"], datetime.now(tz=tzutc())


def get_sql(table_metric):
    if table_metric == 'eth':
        sql_in = "select index, value from {table_name} " \
                 "where host=$host and metric=$eth_in"
        sql_out = "select index, value from {table_name} " \
                  "where host=$host and " \
                  "metric=$eth_out"
        time_query = " and time > now() - {time_delta}"
        sql = f"{sql_in}{time_query};{sql_out}{time_query}"
    else:
        sql = "select index, value from {table_name} " \
              "where host=$host and metric=$metric"
        sql += " and time > now() - {time_delta}"
    return sql


def handle_query_data(table_metric, data):
    if table_metric != 'eth':
        return list(data.get_points())

    ret_in = list(data[0].get_points())
    ret_out = list(data[1].get_points())
    ret = []
    for index, itemd in enumerate(ret_in):
        try:
            value = "{0},{1}".format(
                itemd['value'],
                ret_out[index]['value'],
            )
        except Exception:
            value = "0,0"
        ret.append({'time': itemd['time'], 'value': value})

    return ret


def get_sql_query_data(hostname, table_name, table_metric):
    delta_map = {
        'hour': '1h',
        'day': '1d',
        'week': '1w',
        'month': '31d'
    }
    try:
        # Temporary fixed for bug 245358, need to re-design for 6.4
        time_type = table_name.split('.')[0]
        sql = get_sql(table_metric).format(
            table_name=table_name,
            time_delta=delta_map.get(time_type)
        )
        logger.info("sql: %s", sql)
        data = InfluxClient().get(sql,
                                  epoch='s',
                                  bind_params={
                                      "host": hostname,
                                      "eth_in": "eth_in",
                                      "eth_out": "eth_out",
                                      "metric": table_metric
                                  })
        data = handle_query_data(table_metric, data)
        return [True, data]
    except InfluxDBServerError or InfluxDBClientError as e:
        raise InfluxDBException from e
    except Exception:
        logger.exception('Error Occured when fetch data')
        return [False, []]


def _query_node_running_info(request_data, fixed_offset):
    # return [('c1',[[time,value],..]),..]
    result = []
    monitor_type = request_data['monitor_type']
    # Temporary fixed for bug 245358, need to re-design for 6.4
    time_type = request_data.get('time_type', 'hour')

    db_tables = {
        'gpu': f'{time_type}.gpu_metric',
        'cpu': f'{time_type}.node_metric',
        'memory': f'{time_type}.node_metric',
        'network': f'{time_type}.node_metric',
    }
    db_table = db_tables[monitor_type]
    db_metrics = {
        'gpu': 'gpu_util',
        'cpu': 'cpu_util',
        'memory': 'memory_util',
        'network': 'eth'
    }
    db_metric = db_metrics[monitor_type]

    # The node must exist in the cluster.
    cluster_hostlist = ClusterClient().get_hostlist()
    nodes = list(set(cluster_hostlist) & set(request_data['node']))
    for node in nodes:
        success, query_data = get_sql_query_data(node, db_table, db_metric)
        if not success:
            continue
        if request_data['monitor_type'] == 'network':  # network
            data = {node: [
                ('{0:%Y-%m-%d %H:%M:%S}'.format(
                    datetime.fromtimestamp(
                        int(val['time']), tz=fixed_offset
                    )
                ),
                 '{0}MB / {1}MB'.format(
                     int(float(val['value'].split(',')[0])),
                     int(float(val['value'].split(',')[1])))
                ) for val in query_data
            ]}
        elif request_data['monitor_type'] == 'gpu':
            data = defaultdict(list)
            for val in query_data:
                time_moment = '{0:%Y-%m-%d %H:%M:%S}'.format(
                    datetime.fromtimestamp(int(val['time']), tz=fixed_offset)
                )
                value = '{0}%'.format(float(val['value']))
                gpu_idx = int(val['index'])
                gpu_id = "{0}:{1}".format(node, gpu_idx)
                data[gpu_id].append((time_moment, value))
        else:  # cpu, memory
            data = {node: [
                ('{0:%Y-%m-%d %H:%M:%S}'.format(
                    datetime.fromtimestamp(
                        int(val['time']), tz=fixed_offset
                    )
                ),
                 '{}%'.format((float(val['value'])))
                ) for val in query_data
            ]}
        for id, vals in data.items():
            result.append((id, vals))
    return result


def _query_node_running_statistics(data, fixed_offset):
    start_time, end_time = _get_datetime(data)
    creator, create_time = _get_create_info(data)
    values = _query_node_running_info(data, fixed_offset)
    context = {
        'data': values,
        'start_time': start_time.astimezone(fixed_offset),
        'end_time': end_time.astimezone(fixed_offset),
        'creator': creator,
        'create_time': create_time.astimezone(fixed_offset),
        'operator': settings.LICO.ARCH,
    }
    return context


def get_hostnames_from_filter(filter):
    value_type = filter['value_type']
    values = filter['values']

    # Note: must have one nodename at least for now!
    # Note: only support value_type is hostname for now!
    if isinstance(values, list) \
            and len(values) > 0 \
            and value_type.lower() == 'hostname':
        return values
    else:
        logger.exception(f'Invalid value_type: {value_type}')
        raise InvalidParamException


class UtilizationReportPreview(APIView):
    permission_classes = (AsOperatorRole,)

    def trans_result(self, category, val):
        if category == 'network':
            _in = float(val.split(' / ')[0].split('MB')[0])
            _out = float(val.split(' / ')[1].split('MB')[0])
            val = _in + _out
        else:
            val = val.split('%')[0]
        return str(val)

    @json_schema_validate({
        "type": "object",
        "properties": {
            "filters": {
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
            "timezone_offset": {
                "type": "string",
                'pattern': r'^[+-]?\d+$'
            },
        },
        "required": [
            "filters",
            "timezone_offset"]
    })
    def post(self, request, category):
        format_data = {"total": 0, "data": []}
        node_filter = request.data["filters"]
        filters = get_hostnames_from_filter(node_filter)
        get_tzinfo = int(request.data['timezone_offset'])
        time_type = request.data["filters"].get('time_type', 'hour')

        data = {'start_time': 0, 'end_time': 0, 'creator': '',
                'node': filters, 'monitor_type': category,
                'target': 'node_running_statistics', 'time_type': time_type}
        datas = _query_node_running_statistics(
            data, tzoffset(
                'lico/web', -get_tzinfo * timedelta(minutes=1)
            )
        )

        format_data['data'] = []
        for data in datas['data']:
            values = {"history": [], "hostname": data[0], "type": category}
            for val in data[1]:
                tmp = {"time": val[0], "usage": self.trans_result(
                    category, val[1])}
                values["history"].append(tmp)
            format_data['data'].append(values)

        format_data['total'] = len(datas['data'])
        return Response(format_data)


class ReportDownloadView(APIView):
    permission_classes = (AsOperatorRole,)

    I18N = {
        "memory": {
            "head": [
                "monitor.Node Name",
                [
                    "monitor.Time",
                    "monitor.Mem Usage (%)"
                ]
            ],
            "subtitle": "monitor.Mem Usage",
            "title": "monitor.Node Running Status Report"
        },
        "network": {
            "head": [
                "monitor.Node Name",
                [
                    "monitor.Time",
                    "monitor.Network Usage (up/down)"
                ]
            ],
            "subtitle": "monitor.Network Usage",
            "title": "monitor.Node Running Status Report"
        },
        "cpu": {
            "head": [
                "monitor.Node Name",
                [
                    "monitor.Time",
                    "monitor.CPU Usage (%)"
                ]
            ],
            "subtitle": "monitor.CPU Usage",
            "title": "monitor.Node Running Status Report"
        },
        "gpu": {
            "head": [
                "monitor.Node Name",
                [
                    "monitor.Time",
                    "monitor.GPU Usage (%)"
                ]
            ],
            "subtitle": "monitor.GPU Usage",
            "title": "monitor.Node Running Status Report"
        }
    }

    @json_schema_validate({
        "type": "object",
        "properties": {
            "timezone_offset": {
                "type": "string",
            },
            "language": {
                "type": "string",
            },
            "utilization_report_type": {
                "type": "string",
                # Note: only support value_type is hostname for now!
                "const": "hostname",
            },
            "utilization_report_value": {
                "type": "string",
                # Note: must have one nodename at least for now!
                "minLength": 1,
            },
            "monitor_type": {
                "type": "string",
                "enum": ["network", "cpu", "gpu", "memory"],
            },
            "start_time": {
                "type": "string",
                "pattern": r"\d+",
            },
            "end_time": {
                "type": "string",
                "pattern": r"\d+",
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
        },
        "required": [
            "timezone_offset",
            "language",
            "creator",
            'utilization_report_type',
            'utilization_report_value',
            "monitor_type",
            "page_direction",
            "url",
        ],
        # "additionalProperties": True,
    })
    def post(self, request):
        self.set_language(request)
        # request.POST/GET QueryDict instance is immutable
        request_data = request.data.copy()
        get_tzinfo = int(request_data.get('timezone_offset', 0))
        filename = request_data['url']
        monitor_type = request_data['monitor_type']
        target, ext = path.splitext(filename)
        if target != 'node_running_statistics' \
                or ext not in ['.html', '.pdf', '.xlsx', '.csv']:
            raise InvalidParamException

        request_data['target'] = target
        context = {
            'headline': self.I18N[monitor_type]['head'],
            'title': self.I18N[monitor_type]['title'],
            'subtitle': self.I18N[monitor_type]['subtitle'],
            'doctype': ext[1:],
            'template': path.join('report', target + '.html'),
            'page_direction': request_data['page_direction'],
            'fixed_offset': tzoffset(
                'lico/web', -get_tzinfo * timedelta(minutes=1)
            ),
        }

        request_data["node"] = \
            request_data['utilization_report_value'].split(',')
        try:
            context.update(
                _query_node_running_statistics(
                    request_data, tzoffset(
                        'lico/web', -get_tzinfo * timedelta(minutes=1)
                    )
                )
            )
        except Exception as e:
            msg = f"Generate {target} {ext} report failed!\n {str(e)}"
            logger.exception(msg)
            raise ExportReportException

        stream, filename = GroupReportExporter(**context).report_export()
        response = StreamingHttpResponse(stream)
        response['Content-Type'] = 'application/octet-stream'
        response['Content-Disposition'] = \
            f'attachement;filename="{filename}"'
        return response

    @staticmethod
    def set_language(request):
        set_language = request.data.get('language', False)
        back_language = dict(settings.LANGUAGES)
        if set_language in back_language:
            language = set_language
        else:
            language = settings.LANGUAGE_CODE
        trans_real.activate(language)
