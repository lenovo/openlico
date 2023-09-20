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

import json
import time
from datetime import datetime, timedelta

from dateutil.tz import tzoffset, tzutc
from pandas import DataFrame, isna
from rest_framework.response import Response

from lico.core.contrib.permissions import AsOperatorRole
from lico.core.contrib.views import APIView
from lico.core.job.models import Job
from lico.core.job.utils import (
    get_gres_codes, get_resource_num, get_users_from_filter,
)


def _get_datetime(data):
    return datetime.fromtimestamp(int(data["start_time"]), tz=tzutc()), \
           datetime.fromtimestamp(int(data["end_time"]), tz=tzutc())


class ClusterReportBase:
    @staticmethod
    def query_data(params):
        start_time, end_time = _get_datetime(params)
        filters = json.loads(params["filters"])
        users, queues = [], []
        for _filter in filters:
            if _filter['value_type'].lower() == 'queue':
                queues = [queue.strip() for queue in _filter['values']]
            else:
                users = get_users_from_filter(
                    _filter, ignore_non_lico_user=False
                )
        query = Job.objects.exclude(scheduler_id="", end_time=None)
        if users:
            query = query.filter(submitter__in=users)
        if queues:
            query = query.filter(queue__in=queues)
        query = query.filter(
            submit_time__gte=start_time, submit_time__lte=end_time, state="C"
        )
        return query.as_dict(
            include=['submit_time', 'runtime', 'tres', 'start_time']
        )


class OverallView(ClusterReportBase, APIView):
    permission_classes = (AsOperatorRole,)

    def get(self, request):
        data = self.query_data(request.query_params)
        if not data:
            return Response()
        waiting_th = int(request.query_params['waiting_th'])
        df = DataFrame(data)
        df['waiting_time'] = df['start_time'] - df['submit_time']
        waiting_jobs = df[df['waiting_time'] > waiting_th]

        gres_data = {}
        for gres_code in ['cpu_cores'] + get_gres_codes():
            df[gres_code] = df['tres'].apply(
                get_resource_num, args=(gres_code,)
            )
            df_gres = df[df[gres_code] != 0]
            gres_max = df_gres[gres_code].max()
            gres_mean = df_gres[gres_code].mean()
            gres_data[gres_code] = [
                len(df_gres),
                0 if isna(gres_max) else gres_max,
                0 if isna(gres_mean) else int(round(gres_mean))
            ]

        submit_max = df['runtime'].max()
        submit_mean = df['runtime'].mean()
        waiting_max = waiting_jobs['waiting_time'].max()
        waiting_mean = waiting_jobs['waiting_time'].mean()
        format_data = {
            'submit': [len(df),
                       0 if isna(submit_max) else int(round(submit_max)),
                       0 if isna(submit_mean) else int(round(submit_mean))],
            'waiting': [len(waiting_jobs),
                        0 if isna(waiting_max) else int(round(waiting_max)),
                        0 if isna(waiting_mean) else int(round(waiting_mean))]
        }
        return Response(dict(format_data, **gres_data))


class TrendView(ClusterReportBase, APIView):
    permission_classes = (AsOperatorRole,)

    def get(self, request):
        data = self.query_data(request.query_params)
        if not data:
            return Response()
        waiting_th = int(request.query_params['waiting_th'])
        get_tzinfo = int(request.query_params['timezone_offset'])
        df = DataFrame(data)
        df['waiting_time'] = df['start_time'] - df['submit_time']
        df['date'] = (df['submit_time'] - get_tzinfo*60) // 86400 * 86400
        grouped = df.groupby('date')

        def to_date(timestamp):
            return '{0:%Y-%m-%d}'.format(
                datetime.fromtimestamp(
                    timestamp,
                    tz=tzoffset(
                        'lico/web', -get_tzinfo * timedelta(minutes=1)
                    )
                )
            )

        def values_count(group):
            return len(group[group['waiting_time'] <= waiting_th]),  \
                   len(group[group['waiting_time'] > waiting_th])

        sorted_data = sorted(grouped.apply(values_count).to_dict().items())
        format_data = {
            'dates': map(lambda x: to_date(x[0]), sorted_data),
            'values': map(lambda x: x[1], sorted_data)
        }
        return Response(format_data)


class TimeView(ClusterReportBase, APIView):
    permission_classes = (AsOperatorRole,)

    def get(self, request):
        data = self.query_data(request.query_params)
        if not data:
            return Response()
        waiting_th = int(request.query_params['waiting_th'])
        df = DataFrame(data)
        get_tzinfo = int(request.query_params['timezone_offset'])
        df['waiting_time'] = df['start_time'] - df['submit_time']
        df['date'] = (df['submit_time'] - get_tzinfo * 60) // 86400 * 86400
        df['hour'] = df['submit_time'].apply(
            lambda x: time.localtime(-get_tzinfo * 60 + x).tm_hour // 2
        )
        df['week'] = df['submit_time'].apply(
            lambda x: time.localtime(-get_tzinfo * 60 + x).tm_wday
        )

        def year_day(timestamp):
            time_struct = time.localtime(-get_tzinfo * 60 + timestamp)
            return '{0}{1}'.format(time_struct.tm_year, time_struct.tm_yday)

        def by_hour(group):
            num = len(group.groupby('date'))
            running_num = len(group[group['waiting_time'] <= waiting_th])
            waiting_num = len(group[group['waiting_time'] > waiting_th])
            return [int(round(running_num / num)),
                    int(round(waiting_num / num))]

        def by_week(group):
            num = len(group.groupby('year_day'))
            running_num = len(group[group['waiting_time'] <= waiting_th])
            waiting_num = len(group[group['waiting_time'] > waiting_th])
            return [int(round(running_num / num)),
                    int(round(waiting_num / num))]

        df['year_day'] = df['submit_time'].apply(year_day)
        hour_data = df.groupby('hour').apply(by_hour).to_dict()
        week_data = df.groupby('week').apply(by_week).to_dict()
        format_data = {
            'hour': map(lambda x: hour_data.get(x, [0, 0]), range(12)),
            'week': map(lambda x: week_data.get(x, [0, 0]), range(7))
        }
        return Response(format_data)


class DistributionView(ClusterReportBase, APIView):
    permission_classes = (AsOperatorRole,)

    def get(self, request):
        data = self.query_data(request.query_params)
        if not data:
            return Response()
        df = DataFrame(data)
        gres_codes = get_gres_codes()

        def get_values(row):
            return [row.runtime] + \
                   [row[code] for code in ['cpu_cores'] + gres_codes]

        for gres_code in ['cpu_cores'] + gres_codes:
            df[gres_code] = df['tres'].apply(
                get_resource_num, args=(gres_code,))

        format_data = {
            'keys': ["exec_time", "cpu_cores"] + gres_codes,
            'values': df.apply(get_values, axis=1).to_list()
        }
        return Response(format_data)
