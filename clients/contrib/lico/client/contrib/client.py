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
from os import path

from .exception import NotFound, PermissoinDenied, Unauthorized, UnknownError

logger = logging.getLogger(__name__)


class BaseClient(metaclass=ABCMeta):
    @property
    @abstractmethod
    def app(self) -> str:
        pass

    @staticmethod
    def get_config(settings):  # pragma: no cover
        return settings.GATEWAY

    def __init__(
        self,
        url: str = 'http://127.0.0.1:18080/api/',
        timeout: int = 30,
        username=None, secret=None,
        keyword='jwt', **extra_args
    ):
        from lico.auth.requests import ServiceAuth
        self.url = path.join(url, self.app)
        self.timeout = timeout
        self.username = username
        self.auth = ServiceAuth(
            secret=secret, username=username,
            keyword=keyword, **extra_args
        ) if secret is not None else None

    def get_url(self, uri):
        return path.join(self.url + '/', uri)

    @classmethod
    def from_django_settings(cls, settings):  # pragma: no cover
        from functools import partial
        return partial(
            cls, secret=settings.WEB_SECRET_KEY,
            **{
                key.lower(): value
                for key, value in cls.get_config(settings).items()
            }
        )

    def handle_exception(self, exc, response):
        raise UnknownError(response.text) from exc

    def execute_request(self, *args, **kwargs):
        import requests
        from requests.exceptions import HTTPError

        kwargs.setdefault('auth', self.auth)
        kwargs.setdefault('timeout', self.timeout)

        response = requests.request(
            *args,
            **kwargs
        )
        try:
            response.raise_for_status()
        except HTTPError as e:
            if response.status_code == 401:
                raise Unauthorized from e
            elif response.status_code == 403:
                raise PermissoinDenied from e
            elif response.status_code == 404:
                raise NotFound from e
            else:
                self.handle_exception(e, response)

        return response.json()

    def get(self, *args, **kwargs):  # pragma: no cover
        kwargs.setdefault('allow_redirects', True)
        return self.execute_request('get', *args, **kwargs)

    def options(self, *args, **kwargs):  # pragma: no cover
        kwargs.setdefault('allow_redirects', True)
        return self.execute_request('options', *args, **kwargs)

    def head(self, *args, **kwargs):  # pragma: no cover
        kwargs.setdefault('allow_redirects', False)
        return self.execute_request('head', *args, **kwargs)

    def post(self, *args, **kwargs):  # pragma: no cover
        return self.execute_request('post', *args, **kwargs)

    def put(self, *args, **kwargs):  # pragma: no cover
        return self.execute_request('put', *args, **kwargs)

    def patch(self, *args, **kwargs):  # pragma: no cover
        return self.execute_request('patch', *args, **kwargs)

    def delete(self, *args, **kwargs):  # pragma: no cover
        return self.execute_request('delete', *args, **kwargs)
