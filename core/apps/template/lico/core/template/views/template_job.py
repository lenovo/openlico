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

from rest_framework.response import Response

from lico.core.contrib.authentication import (
    RemoteJWTInternalAuthentication, RemoteJWTWebAuthentication,
)
from lico.core.contrib.views import APIView, InternalAPIView

from ..models import TemplateJob

logger = logging.getLogger(__name__)


class TemplateJobView(APIView):
    authentication_classes = (
        RemoteJWTWebAuthentication,
        RemoteJWTInternalAuthentication,
    )

    def get(self, request, jobid):
        template_job = TemplateJob.objects.get(
            username=request.user.username,
            job_id=jobid
        )
        return Response(
            template_job.as_dict()
        )


class TemplateJobInternalView(InternalAPIView):
    def get(self, request, jobid):
        template_job = TemplateJob.objects.get(
            job_id=jobid
        )
        return Response(
            template_job.as_dict()
        )
