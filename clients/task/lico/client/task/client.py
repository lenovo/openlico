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

from lico.client.contrib.client import BaseClient

from .exception import MaxJobsReachedError

logger = logging.getLogger(__name__)


class Client(BaseClient):
    app = 'builder/container'

    def __init__(
            self,
            url: str = 'http://127.0.0.1:18086/api/',
            *args, **kwargs
    ):
        super().__init__(url, *args, **kwargs)

    def build_job(self, user, prepare, run, output):
        data = dict(
                user=user,
                prepare=prepare,
                run=run,
                output=output,
        )
        res = self.post(
            url=self.get_url(''),
            json=data
        )
        return res['id']

    def query_state(self):
        return self.get(
            url=self.get_url('')
        )

    def cancel_job(self, job_id):
        self.delete(
            url=self.get_url(f'{job_id}/')
        )

    def query_job_state(self, job_id):
        res = self.get(
            url=self.get_url(f'{job_id}/')
        )
        return res

    @staticmethod
    def get_config(settings):  # pragma: no cover
        return settings.BUILDER

    def handle_exception(self, exc, response):
        if response.status_code == 400:
            code = response.json().get('code')
            if code == 9007:
                raise MaxJobsReachedError from exc
        super().handle_exception(exc, response)
