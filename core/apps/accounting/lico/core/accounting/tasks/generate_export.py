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
import time
from datetime import datetime

from django.conf import settings

from lico.core.accounting.charge_job import charge_job

from ..charge_storage import StorageBilling
from ..utils import get_local_timezone
from .billing_statement import BillGroupReportView, get_bill_cycle

logger = logging.getLogger(__name__)


def charge_and_billing():
    timestamp = time.time()
    localtime = datetime.fromtimestamp(timestamp, tz=get_local_timezone())
    # Step1: Charge Storage
    billing_date, _ = get_bill_cycle(localtime)
    try:
        StorageBilling().billing(billing_date)
    except Exception:
        logger.exception(
            'Charge storage failed on %s', billing_date.strftime('%Y-%m-%d')
        )

    # Step 2: charge running job
    if settings.ACCOUNTING.BILLING.JOB_BILLING_CYCLE == 'daily':
        from lico.core.contrib.client import Client
        job_client = Client().job_client()
        running_jobs = job_client.query_running_jobs(verbose=1)
        for job in running_jobs:
            charge_job(job.__dict__)

    # Step 3: Invoke the task for daily billing
    user_daily_billing_report(timestamp)
    admin_daily_billing_report(timestamp)

    # Step 4: Invoke the task for monthly billing if necessary
    trigger_date = int(settings.ACCOUNTING.BILLING.MONTHLY_DAY)
    if localtime.day == trigger_date:
        user_monthly_billing_report(timestamp)
        admin_monthly_billing_report(timestamp)


def user_daily_billing_report(timestamp):
    localtime = datetime.fromtimestamp(timestamp, tz=get_local_timezone())
    BillGroupReportView().save_report('user_daily_report', localtime)
    logger.info('Create all user_daily_report successful!')


def user_monthly_billing_report(timestamp):
    localtime = datetime.fromtimestamp(timestamp, tz=get_local_timezone())
    BillGroupReportView().save_report('user_month_report', localtime)
    logger.info('Create user_month_report successful!')


def admin_daily_billing_report(timestamp):
    localtime = datetime.fromtimestamp(timestamp, tz=get_local_timezone())
    BillGroupReportView().save_report('admin_daily_report', localtime)
    logger.info('Create all admin_daily_report successful!')


def admin_monthly_billing_report(timestamp):
    localtime = datetime.fromtimestamp(timestamp, tz=get_local_timezone())
    BillGroupReportView().save_report('admin_month_report', localtime)
    logger.info('Create admin_month_report successful!')
