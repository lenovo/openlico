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
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from lico.client.contrib.exception import NotFound

from .models import HeartBeat

logger = logging.getLogger(__name__)


def heartbeat_scanner():
    deadline_time = timezone.now() - timedelta(
        seconds=settings.TENSORBOARD.TIMEOUT_SECONDS)
    heartbeat = HeartBeat.objects.filter(recent_time__lt=deadline_time)

    for items in heartbeat:
        job_id = items.job_id
        username = items.username
        try:
            from lico.core.contrib.client import Client
            client = Client().job_client(username=username)
            ret = client.query_job(job_id)

            if ret['state'].lower() == 'c':
                items.delete()
            elif ret['operate_state'] != 'cancelling':
                client.cancel_job(job_id)
        except NotFound:
            logger.info("job %s information is lost", job_id)
