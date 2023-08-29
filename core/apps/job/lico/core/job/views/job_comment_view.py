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

from django.db import transaction
from rest_framework.response import Response

from lico.core.contrib.schema import json_schema_validate
from lico.core.contrib.views import APIView
from lico.core.job.models import Job

logger = logging.getLogger(__name__)


class JobCommentView(APIView):

    @json_schema_validate({
        "type": "object",
        "properties": {
            "user_comment": {
                "type": "string",
                "maxLength": 500
            }
        },
        "required": ["user_comment"],
    })
    def put(self, request, pk):
        with transaction.atomic():
            try:
                job = Job.objects.get(id=pk)
                job.user_comment = request.data['user_comment']
                job.save()
            except Job.DoesNotExist:
                logger.exception("Job does not exist, id: %s", pk)
                raise
        return Response()
