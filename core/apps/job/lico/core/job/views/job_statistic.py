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

import time
from collections import defaultdict
from datetime import datetime

from rest_framework.response import Response

from lico.core.contrib.permissions import AsOperatorRole
from lico.core.contrib.views import APIView

from ..models import Job
from ..utils import get_available_queues, get_timezone


class JobStatisticView(APIView):
    permission_classes = (AsOperatorRole,)

    def get(self, request):
        hours = int(request.query_params.get('time_delta_hour', 0))
        time_stamp = int(time.time()) - (hours * 60 * 60) if hours else 0

        jobs = Job.objects.filter(
            submit_time__gte=datetime.fromtimestamp(time_stamp),
            state__in=['Q', 'R', 'H', 'S']
        )
        available_queues = get_available_queues(request, role='admin')
        queue_dict = {
            queue.name: {
                'running': 0,
                'queuing': 0,
            }
            for queue in available_queues}

        for job in jobs:
            if job.state == 'R':
                queue_dict[job.queue]['running'] += 1
            elif job.state in ('Q', 'H', 'S'):
                queue_dict[job.queue]['queuing'] += 1
        data = [
            {
                'queue': queue_name,
                'running': value['running'],
                'queuing': value['queuing'],
            } for queue_name, value in queue_dict.items()
        ]

        return Response(data)


class JobHistoryStatisticView(APIView):
    permission_classes = (AsOperatorRole,)

    def get(self, request):
        hours = int(request.query_params.get('time_delta_hour', 0))
        timezone_offset = int(request.query_params.get('timezone_offset', 0))
        time_stamp = int(time.time()) - (hours * 60 * 60) if hours else 0
        jobs = Job.objects.filter(
            submit_time__gte=datetime.fromtimestamp(time_stamp)
        ).exclude(scheduler_id="")
        history_jobs = defaultdict(int)
        for job in jobs.iterator():
            submit_date = job.submit_time.astimezone(
                get_timezone(timezone_offset)
            ).strftime('%Y-%m-%d')
            history_jobs[submit_date] += 1

        return Response({
            "total": jobs.count(),
            "avg_per_day": int(sum(history_jobs.values()) / len(history_jobs))
            if len(history_jobs) else 0,
            "max_of_hist": max(history_jobs.values())
            if len(history_jobs) else 0
        })
