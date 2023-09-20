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
from abc import ABCMeta, abstractmethod
from datetime import datetime
from os import path
from typing import Any, Dict

import requests
from dateutil.tz import tzutc
from requests.exceptions import HTTPError

from lico.client.contrib.exception import Unauthorized, UnknownError

from .dataclass import HostPasswd, HostUser, LocalUserNotFound, User

logger = logging.getLogger(__name__)


class AuthClient(metaclass=ABCMeta):
    def __init__(
        self,
        secret,
        url: str = 'http://127.0.0.1:18080/api/',
        timeout: int = 30
    ):
        self.secret = secret
        self.url = url
        self.timeout = timeout

    def auth(self, authorization: str) -> User:
        return self._get_user_info(
            headers={'Authorization': authorization}
        )

    def get_user_info(self, username: str) -> User:
        from lico.auth.requests import ServiceAuth
        return self._get_user_info(
            auth=ServiceAuth(
                secret=self.secret,
                username=username
            )
        )

    def _get_user_info(self, **kwargs):
        response = requests.get(
            url=path.join(self.url, 'user/auth/'),
            timeout=self.timeout,
            **kwargs
        )
        try:
            response.raise_for_status()
        except HTTPError as e:
            if response.status_code == 401:
                logger.exception('Auth Fail: %s', response.json())
                raise Unauthorized from e
            else:
                raise UnknownError from e

        return self.auth_resp_as_object(response.json())

    @abstractmethod
    def auth_resp_as_object(self, response_json: Dict[str, Any]) -> User:
        pass

    @abstractmethod
    def fetch_passwd(self, username: str, raise_exc: bool = True):
        pass


class HostAuthClient(AuthClient):
    def auth_resp_as_object(self, response_json: Dict[str, Any]) -> HostUser:
        return HostUser(
            username=response_json['username'],
            role=response_json['role'],
            date_joined=datetime.fromtimestamp(
                response_json['date_joined'], tz=tzutc()
            ),
            email=response_json['email']
        )

    def fetch_passwd(self, username: str, raise_exc: bool = True):
        passwd = HostPasswd(username=username)
        if raise_exc and passwd._passwd is None:
            raise LocalUserNotFound
        return passwd
