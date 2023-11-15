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

from django.conf import settings
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.response import Response

from lico.core.contrib.dataclass import LocalUserNotFound

from ..authentication import (
    ApiKeyAuthentication, BasicAuthentication, BasicJSONAuthentication,
    JWTWebAuthentication,
)
from . import APIView

logger = logging.getLogger(__name__)


class AuthView(APIView):
    authentication_classes = (
        BasicAuthentication, BasicJSONAuthentication, JWTWebAuthentication,
        ApiKeyAuthentication
    )
    hidden_permission_classes = ()

    def get(self, request):
        user = request.user
        return Response(
            user.as_dict(
                inspect_related=False,
                include=(
                    'username', 'role', 'date_joined', 'context', 'email'
                ),
            )
        )

    def post(self, request):
        return Response(
            dict(
                token=self.build_token(
                    user=request.user,
                    secret=settings.WEB_SECRET_KEY
                )
            )
        )

    def build_token(self, user, secret):
        try:
            from lico.core.contrib.client import Client
            client = Client().auth_client()
            passwd = client.fetch_passwd(username=user.username)
        except LocalUserNotFound as e:
            logger.exception('Local User not exists.')
            raise AuthenticationFailed(
                detail='Local user not exists.'
            ) from e

        return secret.generate_jwt(
            username=user.username,
            expire_minutes=settings.USER.TOKEN.EXPIRE_MINUTES,
            iss='antilles-web-user',
            id=user.id,
            role=user.role,
            workspace=passwd.workspace
        )

