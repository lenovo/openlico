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

from rest_framework.response import Response

from lico.core.contrib.authentication import RemoteJWTInternalAuthentication
from lico.core.contrib.views import InternalAPIView

from ..models import Job


class JobList(InternalAPIView):
    authentication_classes = (
        RemoteJWTInternalAuthentication,
    )

    def post(self, request):
        field_list = [
            "id",
            "submitter",
            "job_running",
            "job_name",
            "state",
            "operate_state",
            "tres",
            "end_time",
        ]
        job_id_list = request.data.get("job_id_list", [])
        submitter = request.data.get("submitter", "")
        query = Job.objects.filter(delete_flag=False, submitter=submitter,
                                   id__in=job_id_list)
        job_list = query.as_dict(include=field_list)
        return Response(job_list)
