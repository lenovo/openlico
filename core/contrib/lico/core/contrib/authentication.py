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

from abc import ABCMeta, abstractmethod

from rest_framework.authentication import (
    BaseAuthentication, get_authorization_header,
)
from rest_framework.exceptions import AuthenticationFailed

from lico.client.auth.client import Unauthorized, UnknownError


class LicoAuthentication(BaseAuthentication, metaclass=ABCMeta):
    @property
    @abstractmethod
    def keyword(self):
        pass

    def authenticate(self, request):
        auth = get_authorization_header(request).split()

        if not auth or auth[0].lower() != self.keyword.lower().encode():
            return None

        return self.authenticate_credentials(
            self.fetch_token(request, auth),
            request=request
        )

    @abstractmethod
    def authenticate_credentials(self, token, request=None):
        pass

    def authenticate_header(self, request):
        return self.keyword

    def fetch_token(self, request, auth):
        import binascii
        if len(auth) == 1:
            raise AuthenticationFailed(
                detail='Invalid token header. No credentials provided.'
            )
        elif len(auth) > 2:
            raise AuthenticationFailed(
                detail='Invalid token header.'
                       'Token string should not contain spaces.'
            )

        try:
            try:
                return auth[1].decode('utf-8')
            except UnicodeDecodeError:
                return auth[1].decode('latin-1')
        except (TypeError, UnicodeDecodeError, binascii.Error) as e:
            raise AuthenticationFailed(
                detail='Invalid token header.'
                       'Token string should not contain invalid characters.'
            ) from e


def _remote_auth(keyword, token):
    from lico.core.contrib.client import Client

    client = Client().auth_client()

    try:
        user = client.auth(f'{keyword} {token}')
    except Unauthorized as e:
        raise AuthenticationFailed(
            detail='Invalie authorization header. '
                   f'Remote authenticate fail: {token}'
        ) from e
    except UnknownError as e:
        raise AuthenticationFailed(
            detail='Unknown Error occured when call remote authenicate:'
        ) from e

    return user, None


class RemoteAuthentication(LicoAuthentication, metaclass=ABCMeta):
    def authenticate_credentials(self, token, request=None):
        return _remote_auth(self.keyword, token)


class RemoteJWTWebAuthentication(RemoteAuthentication):
    keyword = 'jwt'


class RemoteJWTInternalAuthentication(RemoteAuthentication):
    keyword = 'jwt'


class RemoteApiKeyAuthentication(RemoteAuthentication):
    keyword = 'token'


class JWTInternalAnonymousAuthentication(LicoAuthentication):
    keyword = 'jwt'

    @property
    def token(self):
        from django.conf import settings
        secret_key = settings.WEB_SECRET_KEY
        if secret_key is None:
            raise AuthenticationFailed('Secret file not exist.')
        else:
            return secret_key

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

        return None, payload
