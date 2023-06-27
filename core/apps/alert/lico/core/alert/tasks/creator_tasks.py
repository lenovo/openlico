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

from celery.utils.log import get_task_logger
from django.conf import settings
from django.db.transaction import atomic
from django.utils import translation

from lico.core.base.celery import app

from ..models import Alert, Policy

logger = get_task_logger(__name__)


class AlertNoticeBroker(object):

    def handle(self, alert):
        language_code = alert.policy.language
        with translation.override(language_code):
            for func in settings.ALERT.NOTIFICATIONS:
                func(alert)


@app.task(ignore_result=True)
@atomic
def create_alert(alert_data):
    policy_id = alert_data.get("policy_id", None)
    if policy_id is not None:
        try:
            policy = Policy.objects.select_for_update().get(
                id=policy_id, status=Policy.STATUS_CHOICES[0][0]
            )
            alert_data["policy"] = policy
            comment_val = alert_data.pop('comment', None)
            query = Alert.objects.filter(**alert_data).exclude(
                status='resolved'
            )
            if comment_val:
                alert_data['comment'] = comment_val
            if not query.exists():
                alert = Alert.objects.create(**alert_data)
                AlertNoticeBroker().handle(alert)

        except Exception:
            logger.exception("Get Policy failed.")
            raise
