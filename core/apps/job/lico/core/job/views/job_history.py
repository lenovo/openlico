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
import time

from django.utils import timezone
from rest_framework.response import Response

from lico.core.contrib.permissions import AsOperatorRole, AsUserRole
from lico.core.contrib.views import APIView

from ..base.job_state import JobState
from ..exceptions import InvalidParameterException
from ..models import Job

logger = logging.getLogger(__name__)


class JobHistoryView(APIView):
    permission_classes = (AsOperatorRole,)

    def filter_user(self, username):
        is_admin = True
        username = None
        return is_admin, username

    def get(self, request):
        args = self.get_params(request)

        result_data = []
        jobs = Job.objects
        if args['is_admin']:
            job_source = jobs
        else:
            job_source = jobs.filter(
                submitter__exact=args['username'])
        if args['q_name']:
            job_source = job_source.filter(queue__iexact=args['q_name'])
        for dead_time in args['dead_times']:
            point = {
                'time': int(dead_time.timestamp()),
                'timezone': time.timezone
            }
            if args['overall_status'] == "uncompleted":

                point["running"] = self.running_count_at_moment(
                    dead_time, job_source)

                point["waiting"] = self.waiting_count_at_moment(
                    dead_time, job_source)
            else:

                point["completed"] = self.completed_count_at_moment(
                    dead_time, job_source
                )

            result_data.append(point)
        return Response(result_data)

    @staticmethod
    def running_count_at_moment(moment, job_source):
        running_jobs = job_source.filter(
            state__in=JobState.get_running_state_values())
        completed_jobs = job_source.filter(
            state=JobState.COMPLETED.value)

        r_jobs = running_jobs.filter(start_time__lt=moment)
        c_jobs = completed_jobs.filter(
            start_time__lt=moment, end_time__gt=moment)
        jobs = r_jobs | c_jobs

        return jobs.count()

    @staticmethod
    def waiting_count_at_moment(moment, job_source):
        filter_jobs = job_source.exclude(
            operate_state__in=["creating", "create_fail", ""])

        completed_jobs = filter_jobs.filter(
            state=JobState.COMPLETED.value,
            submit_time__lt=moment,
            start_time__gt=moment)

        running_jobs = filter_jobs.filter(
            state__in=JobState.get_running_state_values(),
            submit_time__lt=moment,
            start_time__gt=moment)

        allocating_jobs = filter_jobs.filter(
            state__in=JobState.get_allocating_state_values(),
            submit_time__lt=moment)

        jobs = completed_jobs | running_jobs | allocating_jobs

        return jobs.count()

    @staticmethod
    def completed_count_at_moment(moment, job_source):
        completed_jobs = job_source.filter(state=JobState.COMPLETED.value)
        create_failed_jobs = completed_jobs.filter(
            operate_state="create_fail",
            submit_time__lt=moment)
        create_succeed_jobs = completed_jobs.exclude(
            operate_state="create_fail").filter(end_time__lt=moment)
        jobs = create_failed_jobs | create_succeed_jobs
        return jobs.count()

    def get_params(self, request):
        parameters = {}
        query_params = request.query_params

        num_of_points = int(query_params.get("num_of_points"))
        if num_of_points <= 1:
            raise InvalidParameterException
        duration = int(query_params.get("duration"))
        if duration <= 0:
            raise InvalidParameterException
        parameters['overall_status'] = query_params.get("status")
        if parameters['overall_status'] not in ["completed", "uncompleted"]:
            raise InvalidParameterException
        parameters['q_name'] = query_params.get("q_name", "").strip()

        current_time = time.time()
        parameters['dead_times'] = []
        for i in range(num_of_points):
            value = int(
                current_time - duration + duration / (num_of_points - 1) * i)
            date_time = timezone.datetime.utcfromtimestamp(value)
            parameters['dead_times'].append(timezone.make_aware(date_time))

        parameters['is_admin'], parameters['username'] = self.filter_user(
            request.user.username)

        return parameters


class JobHistoryViewUser(JobHistoryView):
    permission_classes = (AsUserRole,)

    def filter_user(self, username):
        is_admin = False
        username = username
        return is_admin, username
