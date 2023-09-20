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
import time

from django.conf import settings

logger = logging.getLogger(__name__)


class SecretKeyTask:
    is_running = True

    @classmethod
    def get_key_from_db(cls):
        from lico.core.base.models import SecretKey

        db_secret_key = SecretKey.objects.last()
        if db_secret_key and db_secret_key.key:
            return db_secret_key.key.decode()

    @classmethod
    def run(cls, web_secret_key):
        while cls.is_running:
            cls.once(web_secret_key)

            update_interval = settings.USER.KEY.get('UPDATE_INTERVAL')
            time.sleep(update_interval if update_interval else 100)

    @classmethod
    def once(cls, web_secret_key):
        web_secret_key.key_func = cls.get_key_from_db
        web_secret_key.update_keys()

    def terminal(self):
        self.is_running = False
