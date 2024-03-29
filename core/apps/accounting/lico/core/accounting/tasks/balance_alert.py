# Copyright 2023-present Lenovo
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
from django.template.loader import render_to_string

from lico.core.contrib.client import Client
from lico.core.contrib.eventlog import EventLog

from ..models import BalanceAlert, BalanceAlertSetting, BillGroup

logger = logging.getLogger(__name__)

MAX_RETRIES = 3


def format_unit(number):
    unit = settings.ACCOUNTING.BILLING.UNIT
    unit = [u.strip() for u in unit.split(';', 1)]
    if len(unit) == 1:
        return f'{unit[0]}{number:.2f}'
    return f'{unit[0]}{number:.2f}{unit[1]}'


def send_alert_email(targets, alert_bill_groups, threshold):
    if not alert_bill_groups:
        return
    language = settings.ACCOUNTING.BILLING.LANGUAGE
    retries = 0
    while retries < MAX_RETRIES:
        try:
            Client().mail_notice_client().send_message(
                target=targets,
                title=render_to_string(
                    f'email/{language}/balance_alert_title.html'),
                msg=render_to_string(
                    f'email/{language}/balance_alert.html',
                    context={
                        'bill_groups': alert_bill_groups,
                        'threshold': format_unit(threshold)
                    })
            )
            break
        except Exception as e:
            logger.exception(
                'Send balance alert email failed, reason is: %s', e)
            retries += 1
            if retries < MAX_RETRIES:
                time.sleep(30)


def check_balance_and_alert():
    balance_setting = BalanceAlertSetting.objects.first()
    if not balance_setting:
        return
    threshold = balance_setting.balance_threshold
    targets = []
    for target in balance_setting.targets.all():
        targets.extend(target.email)
    if not targets:
        return
    alert_bill_groups = []
    try:
        for bill_group in BillGroup.objects.all():
            if bill_group.balance < threshold and bill_group.balance_alert:
                if not bill_group.alert.exists():
                    alert_bill_groups.append({
                        'id': bill_group.id,
                        'name': bill_group.name,
                        'balance': format_unit(bill_group.balance)
                    })
                    BalanceAlert.objects.create(bill_group_id=bill_group.id)
                    EventLog.opt_create(
                        'root', EventLog.billgroup, EventLog.low_balance,
                        EventLog.make_list(bill_group.id, bill_group.name)
                    )
            else:
                bill_group.alert.all().delete()
    except Exception as e:
        logger.exception('Check bill group balance failed, reason is: %s', e)

    send_alert_email(targets, alert_bill_groups, threshold)
