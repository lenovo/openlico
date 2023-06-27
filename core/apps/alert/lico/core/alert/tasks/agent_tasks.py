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

from os import path
from subprocess import call

from celery.utils.log import get_task_logger
from django.conf import settings

from lico.core.base.celery import app

logger = get_task_logger(__name__)


@app.task(ignore_result=True)
def script(node, level, name, target):
    logger.info('run script: %s', script)
    call(
        [
            path.join(settings.ALERT.SCRIPTS_DIR, target)
        ],
        env={
            'node_name': node,
            'policy_level': level,
            'policy_name': name
        }
    )


@app.task(ignore_result=True)
def email(target, title, msg):
    from lico.core.contrib.client import Client
    client = Client().mail_notice_client()

    client.send_message(target=target, title=title, msg=msg)
