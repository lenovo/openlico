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
from abc import ABCMeta, abstractmethod

from django.conf import settings
from django.contrib.auth import authenticate
from rest_framework.authentication import (
    BasicAuthentication as BaseBasicAuthentication,
)
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied

from lico.core.contrib.authentication import LicoAuthentication

from .exceptions import LoginFail
from .models import User

logger = logging.getLogger(__name__)


def _login(
    userid: str, password: str, request=None
):
    try:
        user: User = User.objects.get(username=userid)
    except User.DoesNotExist as e:
        logger.exception('User[ %s ] not exists', userid)
        raise LoginFail from e

    if not user.is_activate:
        raise LoginFail(user)

    authed_user: User = authenticate(request, user=user, password=password)
    if authed_user is not None:
        user.login_success()
    else:
        user.login_fail()
        logger.info('User[ %s ] authenticated failed', userid)
        raise LoginFail

    return user, None


class BasicAuthentication(BaseBasicAuthentication):
    def authenticate_credentials(
        self, userid: str, password: str, request=None
    ):
        return _login(userid, password, request)

    def authenticate_header(self, request):  # pragma: no cover
        return 'LiCO Basic'


class BasicJSONAuthentication(LicoAuthentication):
    keyword = 'basic-json'

    def fetch_token(self, request, auth):
        if len(auth) > 1:
            raise AuthenticationFailed(
                detail='Invalid token header.'
                       'Token string should be empty.'
            )

        try:
            return request.data['token']
        except KeyError as e:
            raise AuthenticationFailed(
                detail='Invalid token body.'
                       'Token string should not contain invalid characters.'
            ) from e

    def authenticate_credentials(self, token, request=None):
        import binascii
        from base64 import b64decode
        try:
            try:
                token_decoded = b64decode(token).decode('utf-8')
            except UnicodeDecodeError:
                token_decoded = b64decode(token).decode('latin-1')
            token_parts = token_decoded.partition(':')
        except (TypeError, UnicodeDecodeError, binascii.Error) as e:
            raise AuthenticationFailed(
                detail='Invalid basic header.'
                       'Credentials not correctly base64 encoded.'
            ) from e

        userid, password = token_parts[0], token_parts[2]

        return _login(userid, password, request)


class JWTAuthentication(LicoAuthentication, metaclass=ABCMeta):
    def authenticate_credentials(self, token, request=None):
        from jwt import InvalidTokenError
        try:
            payload = self.token.verify_jwt(
                token
            )
        except InvalidTokenError as e:
            raise AuthenticationFailed(
                detail='Invalid token header. JWT decode fail.'
            ) from e

        user = self.get_user(payload)
        return user, payload

    @property
    @abstractmethod
    def token(self):
        pass

    @staticmethod
    @abstractmethod
    def get_user(payload):
        pass


class JWTWebAuthentication(JWTAuthentication):
    keyword = 'jwt'

    @property
    def token(self):
        return settings.WEB_SECRET_KEY

    @staticmethod
    def get_user(payload):
        try:
            user = User.objects.get(username=payload['sub'])
        except User.DoesNotExist as e:
            raise AuthenticationFailed(
                detail='User does not exists.'
            ) from e

        if not user.is_activate:
            raise AuthenticationFailed(
                detail='User has already locked'
            )

        if payload['role'] > user.role:
            raise PermissionDenied(
                'Insufficient permission.'
            )

        return user


class JWTInternalAuthentication(JWTAuthentication):
    keyword = 'lico'

    @property
    def token(self):
        return settings.WEB_SECRET_KEY

    @staticmethod
    def get_user(payload):
        try:
            user = User.objects.get(username=payload['sub'])
        except User.DoesNotExist as e:
            raise AuthenticationFailed(
                detail='User does not exists.'
            ) from e

        if not user.is_activate:
            raise AuthenticationFailed(
                detail='User has already locked'
            )

        return user


class ApiKeyAuthentication(LicoAuthentication):
    keyword = 'token'

    def authenticate_credentials(self, token, request=None):
        try:
            from .models import ApiKey
            user_key = ApiKey.objects.get(api_key=token)
            user = user_key.user
            if user_key.is_activate:
                return user, user_key
            else:
                raise AuthenticationFailed(
                    detail='User is not activate.'
                )
        except ApiKey.DoesNotExist as e:
            raise AuthenticationFailed(
                detail='User does not exists.'
            ) from e
