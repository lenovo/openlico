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

import json
import logging

from django.db.models import Q
from rest_framework.response import Response

from lico.core.contrib.views import APIView

from ..models import Job
from ..utils import get_display_runtime

logger = logging.getLogger(__name__)


class JobLatestViewUser(APIView):

    def get_job_query_set(self, username, count, states):
        q = Q()
        for state in states:
            q |= Q(**state)

        jobs = Job.objects.filter(
            Q(submitter=username) & q
        ).order_by('-id')[:count]
        return jobs

    def get(self, request):
        query_params = request.query_params
        job_count = int(query_params.get("count", 0))
        job_states = query_params.get('job_state', '[]')

        jobs = self.get_job_query_set(
            username=request.user.username,
            count=job_count,
            states=json.loads(job_states),
        ).as_dict(exclude=['job_content', 'delete_flag'])
        for job in jobs:
            job['display_runtime'] = get_display_runtime(
                job['runtime'], job['start_time'], job['state'])
        return Response(jobs)


class JobLatestView(JobLatestViewUser):
    def get_job_query_set(self, username, count, states):
        q = Q()
        for state in states:
            q |= Q(**state)

        jobs = Job.objects.filter(q).order_by('-id')[:count]
        return jobs
