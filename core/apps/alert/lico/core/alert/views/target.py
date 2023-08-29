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

from django.db import IntegrityError, transaction
from rest_framework.response import Response

from lico.core.contrib.permissions import AsAdminRole
from lico.core.contrib.schema import json_schema_validate
from lico.core.contrib.views import APIView

from ..exceptions import AlarmTargetExistsException
from ..models import NotifyTarget

logger = logging.getLogger(__name__)


class TargetView(APIView):
    permission_classes = (AsAdminRole,)

    def get(self, request):
        return Response(
            NotifyTarget.objects.as_dict(
                inspect_related=False
            )
        )

    @json_schema_validate({
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "phone": {
                "type": "array",
                "items": {"type": "string", "format": "phone"}
            },
            "email": {
                "type": "array",
                "items": {"type": "string", "format": "email"}
            }
        },
        "required": ["phone", "email", "name"]
    })
    def post(self, request):
        data = request.data
        try:
            NotifyTarget.objects.create(**data)
        except IntegrityError as e:
            raise AlarmTargetExistsException from e
        return Response()


class TargetDetailView(APIView):
    permission_classes = (AsAdminRole,)

    def get(self, request, pk):
        target = NotifyTarget.objects.get(pk=pk)
        return Response(
            target.as_dict(inspect_related=False)
        )

    @json_schema_validate({
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "phone": {
                "type": "array",
                "items": {"type": "string", "format": "phone"}
            },
            "email": {
                "type": "array",
                "items": {"type": "string", "format": "email"}
            }
        },
        "required": ["phone", "email", "name"]
    })
    @transaction.atomic
    def put(self, request, pk):
        target = NotifyTarget.objects.select_for_update().get(pk=pk)
        target.name = request.data['name']
        target.phone = request.data['phone']
        target.email = request.data['email']
        target.save()
        return Response()

    def delete(self, request, pk):
        NotifyTarget.objects.get(pk=pk).delete()
        return Response()
