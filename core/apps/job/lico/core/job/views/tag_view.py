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

from django.db import transaction
from rest_framework.response import Response

from lico.core.contrib.schema import json_schema_validate
from lico.core.contrib.views import APIView

from ..helpers.tag_helper import add_tags_to_one_job, get_all_tags
from ..models import Job, Tag

logger = logging.getLogger(__name__)


class TagView(APIView):

    def get(self, request):
        username = request.user.username
        tag_number = request.query_params.get('count', 20)
        tags = Tag.objects.filter(
            username=username).order_by(
            "-count", "-update_time")[:int(tag_number)]
        return Response({"tags": tags.values_list("name", flat=True)})

    @json_schema_validate({
        "type": "object",
        "properties": {
            "job_id": {
                "type": "array",
                "items":
                    {
                        "type": "integer",
                    }
            },
            "tags": {
                "type": "array",
                "items":
                    {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 24,
                    }
            }
        },
        "required": ["job_id", "tags"],
    })
    def put(self, request):
        jobs_id = request.data['job_id']
        tags_list = request.data['tags']
        username = request.user.username
        jobs = Job.objects.filter(submitter=username, id__in=jobs_id)
        tags = get_all_tags(username, tags_list)
        success = set()
        for job in jobs:
            try:
                with transaction.atomic():
                    add_tags_to_one_job(job, tags)
                    success.add(job.id)
            except Exception:
                logger.exception(
                    "Add job tags failed. Error job id: %s", job.id)
        return Response({"failed": set(jobs_id) - success})

    @json_schema_validate({
        "type": "object",
        "properties": {
            "job_id": {
                "type": "array",
                "items":
                    {
                        "type": "integer",
                    }
            },
            "tags": {
                "type": "array",
                "items":
                    {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 24,
                    }
            }
        },
        "required": ["job_id"],
    })
    def delete(self, request):
        jobs_id = request.data['job_id']
        jobs = Job.objects.filter(
            submitter=request.user.username, id__in=jobs_id)
        success = set()
        for job in jobs:
            try:
                with transaction.atomic():
                    if 'tags' in request.data:
                        original_tags = job.tags.exclude(
                            name__in=request.data['tags'])
                        job.tags.set(original_tags)
                        success.add(job.id)
                    else:
                        job.tags.set([])
                        success.add(job.id)
            except Exception:
                logger.exception(
                    "Clear job tags failed. Error job id: %s", job.id)

        return Response({"failed": set(jobs_id) - success})
