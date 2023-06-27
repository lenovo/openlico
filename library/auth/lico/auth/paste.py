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

from .db import AuthDatabase
from .secret import SharedSecret

logger = logging.getLogger(__name__)


def service_auth_filter_factory(
        global_conf, verify='true',
        allow_anonymous_user='true',
        key_storage='db',
        token_expire_minute=60,
        key_expire_day=3,
        **kwargs
):
    def filter(app):
        return ServiceAuthFilter(
            app,
            verify=(verify == 'true'),
            allow_anonymous_user=(allow_anonymous_user == 'true'),
            key_storage=key_storage,
            token_expire_minute=token_expire_minute,
            key_expire_day=key_expire_day,
            **kwargs
        )

    return filter


class ServiceAuthFilter:
    keyword = 'lico'

    def __init__(
            self, app, verify=True,
            allow_anonymous_user=True,
            key_storage='db',
            token_expire_minute=60,
            key_expire_day=3,
            **kwargs
    ):
        self.app = app
        self.verify = verify
        self.allow_anonymous_user = allow_anonymous_user
        self.key_storage = key_storage
        if self.key_storage == 'db':
            self.db = AuthDatabase(**kwargs)
            self.secret = SharedSecret(key=self.db.get_key())
            self.secret.keys.token_expire_minute = token_expire_minute
            self.secret.keys.key_expire_day = key_expire_day
        else:
            raise Exception("key_storage only have db type.")

    def __call__(self, environ, start_response):
        auth = environ.get('HTTP_AUTHORIZATION', '').split()

        if not auth or \
                auth[0].lower() != self.keyword.lower() or \
                len(auth) == 1:
            return self.response_401(
                start_response,
                'Invalid token header. No credentials provided.'
            )
        elif len(auth) > 2:
            return self.response_401(
                start_response,
                'Invalid token header.'
                'Token string should not contain spaces.'
            )

        verify_method = getattr(self, '_verify_from_' + self.key_storage)
        from jwt import InvalidTokenError
        try:
            payload = verify_method(auth)
        except InvalidTokenError:
            logger.warning("invalid token", exc_info=True)
            return self.response_401(
                start_response,
                'Invalid token header. JWT decode fail.'
            )

        if not self.allow_anonymous_user:
            if not payload['sub']:
                return self.response_401(
                    start_response,
                    'Do not allow anonymous user.'
                )

        environ['X-LICO-JWT-PAYLOAD'] = payload

        return self.app(environ, start_response)

    def _verify_from_db(self, auth):
        self.secret.key_func = self.db.get_key

        return self.secret.verify_jwt(
            auth[1], verify=self.verify
        )

    @staticmethod
    def response_401(start_response, message):
        logger.warning("auth fail, reason: %s", message)
        start_response(
            '401 UNAUTHORIZED', [('Content-type', 'application/json')])
        return [
            json.dumps({'msg': message}).encode()
        ]
