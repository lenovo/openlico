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

from datetime import timedelta

from django.db.transaction import atomic
from django.utils.timezone import now
from rest_framework.response import Response

from lico.core.contrib.permissions import AsAdminRole
from lico.core.contrib.schema import json_schema_validate

from ..models import User
from . import APIView


class LockView(APIView):
    permission_classes = (AsAdminRole,)

    @json_schema_validate({
        'type': 'object',
        'properties': {
            'days': {
                'type': 'integer',
                'minimum': 0,
                'maximum': 999
            },
            'hours': {
                'type': 'integer',
                'minimum': 0,
                'maximum': 999
            },
        },
        'required': ['days', 'hours'],
    })
    @atomic
    def post(self, request, pk):
        user = User.objects.select_for_update().get(
            role__lt=User.ADMIN_ROLE, id=pk
        )
        user.fail_chances = 0
        user.effective_time = now() + timedelta(
            days=request.data["days"],
            hours=request.data["hours"]
        )
        user.save()
        return Response()

    @atomic
    def delete(self, request, pk):
        user = User.objects.select_for_update().get(pk=pk)
        user.effective_time = now()
        user.fail_chances = 0
        user.save()
        return Response()
