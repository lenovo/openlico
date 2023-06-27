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
from datetime import timedelta

from django.db.models import Q
from django.utils.timezone import now
from rest_framework.response import Response

from lico.core.contrib.authentication import RemoteJWTInternalAuthentication
from lico.core.contrib.views import InternalAPIView

from ..base.job_state import JobState
from ..models import Job

logger = logging.getLogger(__name__)


class RecentJobListView(InternalAPIView):

    def get(self, request):
        end_time_offset = int(request.query_params.get('end_time_offset', 300))
        q = Q(state=JobState.RUNNING.value)

        if end_time_offset:
            q |= Q(end_time__gte=(
                    now()-timedelta(seconds=end_time_offset)
            ))

        recent_jobs = Job.objects.filter(Q(delete_flag=False) & q)
        return Response(recent_jobs.as_dict(
            exclude=['job_content', 'delete_flag']
        ))


class UserRecentJobListView(InternalAPIView):
    authentication_classes = (
        RemoteJWTInternalAuthentication,
    )

    def get(self, request):
        end_time_offset = int(request.query_params.get('end_time_offset', 300))
        q = Q(state=JobState.RUNNING.value)

        if end_time_offset:
            q |= Q(end_time__gte=(
                    now()-timedelta(seconds=end_time_offset)
            ))

        recent_jobs = Job.objects.filter(
            Q(delete_flag=False) &
            Q(submitter=request.user.username) &
            q
        )
        return Response(recent_jobs.as_dict(
            exclude=['job_content', 'delete_flag']
        ))
