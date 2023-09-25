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

from django.conf import settings
from django.contrib.auth import authenticate
from django.db.transaction import atomic
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.response import Response

from lico.core.contrib.permissions import AsAdminRole
from lico.core.contrib.schema import json_schema_validate

from ..libuser import Libuser
from ..models import User
from ..pam import change_password
from . import APIView


class ChangePasswordView(APIView):

    @json_schema_validate({
        'type': 'object',
        'properties': {
            'new_password': {
                'type': 'string',
                'minLength': 1
            },
            'old_password': {
                'type': 'string',
                'minLength': 1
            }
        },
        'required': [
            'new_password',
            'old_password'
        ]
    })
    def patch(self, request):
        user = request.user

        old_password = request.data['old_password']
        new_password = request.data['new_password']

        if authenticate(user=user, password=old_password) is None:
            raise AuthenticationFailed

        if old_password == new_password:
            return Response()

        if settings.USER.USE_LIBUSER:
            Libuser().modify_user_pass(
                user.username, new_password
            )
        else:
            change_password(user.username, new_password)

        return Response()


class ModifyPasswordView(APIView):
    permission_classes = (AsAdminRole,)

    @json_schema_validate({
        'type': 'object',
        'properties': {
            'password': {
                'type': 'string',
                'minLength': 1
            }
        },
        'required': [
            'password'
        ]
    })
    @atomic
    def put(self, request, pk):
        new_password = request.data['password']

        user = User.objects.select_for_update().get(
            pk=pk, role__lt=User.ADMIN_ROLE
        )

        if settings.USER.USE_LIBUSER:
            Libuser().modify_user_pass(user.username, new_password)
        else:
            change_password(user.username, new_password)

        return Response()
