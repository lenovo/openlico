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

import grp

from django.conf import settings
from rest_framework.response import Response

from lico.core.contrib.permissions import AsAdminRole, AsOperatorRole
from lico.core.contrib.schema import json_schema_validate

from ..exceptions import (
    GroupAlreadyExist, InvalidLibuserOperation, InvalidOperation,
)
from ..libuser import Libuser
from . import APIView


class GroupListView(APIView):
    permission_classes = (AsAdminRole, )

    @AsOperatorRole
    def get(self, request):
        if settings.USER.USE_LIBUSER:
            groups = Libuser().get_all_groups()
        else:
            groups = [
                {'name': g.gr_name, 'gid': g.gr_gid}
                for g in grp.getgrall()
                if g.gr_gid >= settings.USER.NSS.MIN_GID
            ]
        return Response(groups)

    @json_schema_validate({
        'type': 'object',
        'properties': {
            'name': {
                'type': 'string',
                'minLength': 1
            }
        },
        'required': ['name']
    })
    def post(self, request):
        group_name = request.data['name']
        try:
            Libuser().add_group(group_name)
        except RuntimeError as e:
            raise GroupAlreadyExist from e
        return Response(
            {'name': group_name}
        )


class GroupDetailView(APIView):
    permission_classes = (AsAdminRole,)

    def delete(self, request, name):
        try:
            Libuser().remove_group(name)
        except InvalidOperation as e:
            raise InvalidLibuserOperation from e
        return Response()
