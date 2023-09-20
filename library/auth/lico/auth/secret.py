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

import jwt
from cryptography.fernet import Fernet
from jwt import DecodeError

from .key import KeyGroup


class Secret:
    def __init__(self, key):
        self._fernet = Fernet(key=key)
        self.key = key

    @classmethod
    def generate(cls):
        return cls(
            key=Fernet.generate_key()
        )

    def generate_jwt(
            self, username=None,
            expire_minutes=15, effect_minutes=1,
            algorithms='HS512',
            iss='antilles-internal-user',
            **extra_args
    ):
        from datetime import datetime, timedelta

        from dateutil.tz import tzutc

        now = datetime.now(tzutc())

        encoded_jwt = jwt.encode(
            dict({
                'iss': iss,
                'sub': username,
                'iat': now,
                'nbf': now - timedelta(minutes=effect_minutes),
                'exp': now + timedelta(minutes=expire_minutes),
                'jti': Fernet.generate_key().decode()
            }, **extra_args),
            self.key,
            algorithm=algorithms
        )
        if isinstance(encoded_jwt, bytes):  # pragma: no cover
            encoded_jwt = encoded_jwt.decode()
        return encoded_jwt

    def verify_jwt(
            self, token,
            algorithms='HS512', verify=True,
            **extra_options
    ):
        return jwt.decode(
            token, self.key,
            options=dict({
                'verify_signature': verify,
                'verify_exp': verify,
                'verify_nbf': verify,
                'verify_iat': verify,
                'require_exp': True,
                'require_nbf': True,
                'require_iat': True,
                'require_iss': True,
                'require_jti': True,
                'require_sub': True,
                'require_mgt': True
            }, **extra_options),
            algorithms=[algorithms]
        )

    def encrypt(self, data):
        return self._fernet.encrypt(data)

    def decrypt(self, token, ttl=None):
        return self._fernet.decrypt(token=token, ttl=ttl)


class SharedSecret(Secret):

    def __init__(self, key):
        super().__init__(key=key)
        self.keys = KeyGroup()
        self.key_func: callable = None  # function that get lastest key

    def verify_jwt(self, token, algorithms='HS512', verify=True,
                   **extra_options):

        if self.keys.latest.key:
            for key in [self.keys.latest] + self.keys.history:
                if key.is_valid():
                    self.key = key.key
                    try:
                        payload = super().verify_jwt(token, algorithms,
                                                     verify, **extra_options)
                    except DecodeError:
                        continue
                    else:
                        return payload

        self.key = self.update_keys()
        payload = super().verify_jwt(token, algorithms,
                                     verify, **extra_options)
        return payload

    def generate_jwt(
            self, username=None,
            expire_minutes=15, effect_minutes=1,
            algorithms='HS512',
            iss='antilles-internal-user',
            **extra_args
    ):
        if self.keys.latest.key is None:
            self.update_keys()
        self.key = self.keys.latest.key
        return super().generate_jwt(username,
                                    expire_minutes,
                                    effect_minutes,
                                    algorithms,
                                    iss,
                                    **extra_args
                                    )

    def update_keys(self):
        if self.key_func:
            db_key = self.key_func()
            if db_key:
                self.keys.update(db_key)
                self.keys.clear_expired()

                return db_key


class LatestSecret(Secret):  # pragma: no cover

    def __init__(self, db_host, db_database, db_port):
        from lico.auth.db import AuthDatabase

        self.db = AuthDatabase(db_host=db_host,
                               db_database=db_database,
                               db_port=db_port)
        key = self.db.get_key()
        super().__init__(key=key)

    @property
    def key(self):
        return self.db.get_key()

    @key.setter
    def key(self, key):
        if not self.key:
            self.key = key

