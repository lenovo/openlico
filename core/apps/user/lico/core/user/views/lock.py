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

from datetime import MAXYEAR, date, timedelta

from django.conf import settings
from django.db.transaction import atomic
from django.utils.timezone import now
from rest_framework.response import Response

from lico.core.contrib.permissions import AsAdminRole
from lico.core.contrib.schema import json_schema_validate

from ..libuser import Libuser
from ..models import User
from ..utils import require_libuser
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

        if settings.USER.USE_LIBUSER:
            # Ensure ssh access is allowed again
            Libuser().modify_user_lock(user.username, lock=False)

        return Response()


class FullLockView(APIView):
    permission_classes = (AsAdminRole,)

    @atomic
    @require_libuser
    def post(self, request, pk):
        """Denies access of a certain user to web portal and also
        denies ssh access to the cluster
        """
        user = User.objects.select_for_update().get(
            role__lt=User.ADMIN_ROLE, id=pk
        )
        # Deny web access
        user.fail_chances = 0
        user.effective_time = date(year=MAXYEAR, month=12, day=31)
        user.save()

        # Deny ssh access
        Libuser().modify_user_lock(user.username, lock=True)

        return Response()
