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

from lico.client.contrib.client import BaseClient

logger = logging.getLogger(__name__)


class MailClient(BaseClient):
    app = 'notice/mail'

    def __init__(
        self,
        url: str = 'http://127.0.0.1:18091/api/',
        *args, **kwargs
    ):
        super().__init__(url, *args, **kwargs)

    def send_message(self, target, title, msg):
        self.post(
            url=self.get_url(''),
            json=dict(
                target=target,
                title=title,
                msg=msg
            )
        )

    @staticmethod
    def get_config(settings):  # pragma: no cover
        return settings.MAIL
