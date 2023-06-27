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
from collections import Counter, defaultdict
from functools import reduce

from rest_framework.response import Response

from lico.core.contrib.views import InternalAPIView

from ..base.job_state import JobState
from ..models import Job, JobRunning
from ..utils import convert_tres

logger = logging.getLogger(__name__)


class RunningJobResourceView(InternalAPIView):

    def get(self, request):
        running_jobs_tres_list = Job.objects.filter(
            state=JobState.RUNNING.value
        ).values_list('tres', flat=True)
        tres_list = list(map(convert_tres, running_jobs_tres_list))
        data = reduce(lambda x, y: x + y, tres_list) \
            if tres_list else Counter()
        return Response({
            'core_total_num': data['core_total_num'],
            'gpu_total_num': data['gpu_total_num']
        })


class HostResourceUsedView(InternalAPIView):
    def get(self, request):
        response_value = defaultdict(Counter)
        running_jobs_tres_list = JobRunning.objects.filter(
            job__state=JobState.RUNNING.value
        ).values("hosts", "per_host_tres")
        for job_tres in running_jobs_tres_list:
            tres_counter = convert_tres(job_tres['per_host_tres'])
            for nodename in job_tres['hosts'].split(','):
                response_value[nodename]['runningjob_num'] += 1
                response_value[nodename].update(tres_counter)
        response_value = {
            nodename: {
                'runningjob_num': resource['runningjob_num'],
                'core_total_num': resource['core_total_num'],
                'gpu_total_num': resource['gpu_total_num']
            }
            for nodename, resource in response_value.items()
        }
        return Response(response_value)


class RunningJobsDetailView(InternalAPIView):
    def get(self, request):
        field_list = [
            "id",
            "submitter",
            "scheduler_id",
            "job_running",
            "job_name",
            "workspace",
            "tres",
            "queue",
            "submit_time",
        ]
        verbose = int(request.query_params.get("verbose", 0))
        if verbose == 1:
            field_list += [
                "identity_str",
                "start_time",
                "end_time",
                "scheduler_state",
                "state",
                "runtime",
                "create_time",
                "update_time",
            ]
        running_jobs = Job.objects.filter(
            state=JobState.RUNNING.value,
            delete_flag=False
        ).as_dict(include=field_list)
        return Response(running_jobs)
