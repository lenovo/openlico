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


import json
import logging

from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView as BaseAPIView

from lico.core.accounting.exceptions import (
    CreateBillGroupUserRelationException,
)
from lico.core.accounting.models import BillGroup, UserBillGroupMapping
from lico.core.contrib.permissions import AsAdminRole, AsUserRole
from lico.core.contrib.schema import json_schema_validate
from lico.core.contrib.views import APIView, InternalAPIView

from ..serializers import UserBillGroupSerializer

logger = logging.getLogger(__name__)


class BaseUserBillGroupView(BaseAPIView):
    def post(self, request):
        username_list = request.data.get('name', [])
        if not username_list:
            data = UserBillGroupMapping.objects.as_dict(
                include=['username', 'bill_group']
            )
        else:
            if isinstance(username_list, str):
                username_list = json.loads(username_list)
            data = UserBillGroupMapping.objects.filter(
                username__in=username_list
            ).as_dict(include=['username', 'bill_group'])
        return Response(dict([(x['username'], x['bill_group']) for x in data]))

    @json_schema_validate({
        "type": "object",
        "properties": {
            "user_billgroup_pairs": {
                "type": "object",
                "additionalProperties": {
                    "type": "integer"
                }
            },
        },
        "required": [
            "user_billgroup_pairs",
        ]
    })
    def put(self, request):
        user_billgroup_mapping = request.data.get("user_billgroup_pairs", {})
        # {<username>: <bill_group_id>}
        for username, bill_group_id in user_billgroup_mapping.items():
            try:
                with transaction.atomic():
                    UserBillGroupMapping.objects.update_or_create(
                        username=username,
                        defaults=dict(bill_group_id=bill_group_id)
                    )
                    logger.debug(
                        f"Successfully created or updated user {username} and "
                        f"billing group {bill_group_id} mapping relationship"
                    )
            except IntegrityError as e:
                logger.exception(
                    f"Failed to create or update user {username} and "
                    f"billing group {bill_group_id} mapping relationship"
                )
                raise CreateBillGroupUserRelationException from e

        return Response({})


class UserBillGroupView(BaseUserBillGroupView, APIView):
    permission_classes = (AsAdminRole,)

    @AsUserRole
    def get(self, request):
        try:
            ubg_mapping = UserBillGroupMapping.objects.get(
                username=self.request.user.username
            )
            return Response(
                UserBillGroupSerializer(ubg_mapping).data,
                status=status.HTTP_200_OK
            )
        except UserBillGroupMapping.DoesNotExist:
            # user does not belong to any billing group
            return Response(
                {
                    'username': self.request.user.username,
                    'bill_group': None,
                },
                status=status.HTTP_200_OK
            )

    @AsUserRole
    @json_schema_validate({
        "type": "object",
        "properties": {
            "name": {
                "type": "array",
                "items": {
                    "type": "string",
                    "minLength": 1
                },
            },
        },
        "required": [
            "name",
        ]
    })
    def post(self, request):
        return super().post(request)

    @json_schema_validate({
        "type": "object",
        "properties": {
            "user_billgroup_pairs": {
                "type": "object",
                "additionalProperties": {
                    "type": "integer"
                }
            },
        },
        "required": [
            "user_billgroup_pairs",
        ]
    })
    def put(self, request):
        return super().put(request)

    def delete(self, request):
        data = json.loads(request.body)
        username_list = data.get("username_list")
        for username in username_list:
            try:
                UserBillGroupMapping.objects.get(
                    username=username).delete()
            except UserBillGroupMapping.DoesNotExist:
                logger.exception(
                    f"User {username} has no relationship with any billgroup."
                )
                continue

        return Response()


class InternalUserBillGroupView(BaseUserBillGroupView, InternalAPIView):
    def post(self, request):
        return super().post(request)

    def put(self, request):
        return super().put(request)


class BillGroupUserListView(InternalAPIView):

    @json_schema_validate({
        "type": "object",
        "properties": {
            "bill_group_list": {
                "type": "array",
                "items": {
                    "type": "integer"
                }
            }
        },
        "required": ["bill_group_list"]
    })
    def post(self, request):
        billgroup_user_mapping = {}
        # {<bill_group_id>:[<username>,<username>]}
        bill_group_list = request.data.get('bill_group_list', '[]')
        for bill_group_id in bill_group_list:
            username_list = UserBillGroupMapping.objects.filter(
                bill_group_id=bill_group_id
            ).values_list("username", flat=True)
            if not username_list:
                logger.debug(
                    f'The billing group {bill_group_id} does not have a '
                    f'mapping relationship with users'
                )
            billgroup_user_mapping[bill_group_id] = list(username_list)
        return Response(billgroup_user_mapping)


class InternalBillGroupListView(InternalAPIView):
    def get(self, request):
        return Response(BillGroup.objects.all().as_dict(
            include=["id", "name"]
        ))
