# -*-coding:utf-8 -*-
# Copyright 2018-present Lenovo
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
from collections import Counter

from django.db import transaction
from rest_framework.response import Response

from lico.core.contrib.schema import json_schema_validate
from lico.core.contrib.views import APIView

from ..exceptions import (
    FavoTemplateExistsException, FavoTemplateNotExistException,
)
from ..models import FavoriteTemplate, TemplateJob

logger = logging.getLogger(__name__)


class RecentTemplateView(APIView):
    def get(self, request):
        jobs = TemplateJob.objects.filter(
            username=request.user.username
        ).order_by('-create_time')[:100].values_list(
            "template_code",
            flat=True
        )
        return Response(
            [
                {"template_code": key, "count": value}
                for key, value in Counter(jobs).items()
            ]
        )


class FavoriteTemplateListView(APIView):
    @json_schema_validate({
        "type": "object",
        "properties": {
            "code": {"type": "string"},
        },
        "required": ["code"]
    })
    def post(self, request):
        with transaction.atomic():
            username = request.user.username
            template_code = request.data['code']
            type = 'MyTemplate' if \
                template_code.isdigit() else 'Standard'

            if FavoriteTemplate.objects.filter(
                    username=username, code=template_code):
                logger.error('%s favorite template %s already exists.',
                             request.user.username, template_code)
                raise FavoTemplateExistsException

            FavoriteTemplate.objects.create(
                username=username,
                code=template_code,
                type=type
            )

        return Response()

    def get(self, request):
        username = request.user.username
        favo_templates = FavoriteTemplate.objects.filter(username=username)

        favo_template_list = [favo_template.as_dict()
                              for favo_template in favo_templates]

        return Response(favo_template_list)


class FavoriteTemplateView(APIView):
    def delete(self, request, code):
        with transaction.atomic():
            try:
                username = request.user.username
                job_template = FavoriteTemplate.objects.get(
                    username=username,
                    code=code)
            except FavoriteTemplate.DoesNotExist as e:
                message = "Delete {0} favorite template {1} failed, " \
                          "FavoriteTemplate objects not exist."\
                    .format(request.user.username, code)
                logger.exception(message)
                raise FavoTemplateNotExistException from e

            job_template.delete()

        return Response()
