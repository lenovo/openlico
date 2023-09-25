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

import calendar
import logging
import sys
from datetime import datetime, timedelta
from os import environ, path
from subprocess import CalledProcessError  # nosec B404

from dateutil.parser import parse
from django.core.management import BaseCommand
from django.db.models import Sum

from lico.core.accounting.charge_job import charge_job
from lico.core.accounting.charge_storage import StorageBilling
from lico.core.accounting.exceptions import UserBillGroupNotExistException
from lico.core.accounting.models import JobBillingStatement
from lico.core.accounting.utils import get_local_timezone
from lico.core.contrib.client import Client

logger = logging.getLogger(__name__)


def print_red(string):
    print('\033[31m{}\033[0m'.format(string))


def print_green(string):
    print('\033[92m{}\033[0m'.format(string))


class Command(BaseCommand):
    help = 'Sync billing statement (include jobs billing and storage billing)'

    def add_arguments(self, parser):
        parser.add_argument(
            '-s', '--starttime', required=True,
            help='start time. Time Format: YYYY-MM-DD. e.g. 2020-01-01',
        )
        parser.add_argument(
            '-e', '--endtime', required=True,
            help='end time. Time Format: YYYY-MM-DD. e.g. 2020-01-02',
        )

        billing_statement_type_group = parser.add_mutually_exclusive_group()
        billing_statement_type_group.add_argument(
            '--job', action='store_true',
            help='only sync job billing statement')
        billing_statement_type_group.add_argument(
            '--storage', action='store_true',
            help='only sync storage billing statement')

    def handle(self, *args, **options):
        log_file_path = path.join(
            environ.get("LICO_LOG_FOLDER"), 'sync_billing_statement.log'
        )
        logging.basicConfig(
            filename=log_file_path,
            level=logging.INFO,
            format='%(asctime)s: [%(levelname)s] %(message)s'
        )
        try:
            start_time = parse(
                options['starttime'],
            ).replace(
                hour=0, minute=0, second=0, microsecond=0,
                tzinfo=get_local_timezone()
            )
            end_time = parse(
                options['endtime'],
            ).replace(
                hour=23, minute=59, second=59, microsecond=999999,
                tzinfo=get_local_timezone()
            )
        except Exception:
            print_red("Date time format error, Time Format: "
                      "YYYY-MM-DD. e.g. 2020-01-01")
            sys.exit(1)
        if start_time > end_time:
            print_red("End time is earlier than start time")
            sys.exit(1)

        msg = "Start to sync billing statement, the sync interval is " \
              "{0} - {1}".format(start_time, end_time)
        logger.info(msg)
        print(msg)

        if not options['storage']:
            # Sync history job billing statement
            job_ids = set(self._sync_history_job(start_time, end_time))
            self._sync_job_billing_statement(job_ids)

        if not options['job']:
            # Sync storage billing statement
            self._sync_storage_billing_statement(start_time, end_time)

        logger.info("Sync billing statement finished.")
        print("Sync billing statement log: {}".format(log_file_path))

    @classmethod
    def _sync_history_job(cls, start_time, end_time):
        from math import ceil
        interval = timedelta(hours=1)
        exclude_ids = cls._get_charged_job_id(start_time, end_time)
        sync_number = int(ceil(
            (end_time - start_time).total_seconds() / interval.total_seconds()
        ))

        for number in range(sync_number):
            sync_start_time = start_time + number * interval
            sync_end_time = end_time
            if sync_end_time - sync_start_time > interval:
                sync_end_time = sync_start_time + (
                    interval - timedelta(microseconds=1)
                )

            try:
                job_client = Client().job_client()
                ret = job_client.sync_history_job(
                    calendar.timegm(sync_start_time.timetuple()),
                    calendar.timegm(sync_end_time.timetuple()),
                    exclude_ids
                )
            except Exception:
                print_red("Failed to get history jobs.")
                return
            for job_id in ret:
                yield job_id

    @classmethod
    def _sync_job_billing_statement(cls, jobids):
        charge_jobs = []
        tmp_stdout_msg = \
            "{time} " \
            "Already charged jobs records: {already_charged_jobs_count}; " \
            "New charged jobs records: {charged_jobs_count}; " \
            "No user-billing mapping jobs: {no_user_billing_mapping_count}; " \
            "Charge jobs failed: {failed_charged_jobs_count}"
        tmp_stdout_jobids = {
            "already_charged_jobs_count": 0,
            "charged_jobs_count": 0,
            "no_user_billing_mapping_count": 0,
            "failed_charged_jobs_count": 0
        }
        for job_id in jobids:
            try:
                job_client = Client().job_client()
                job = job_client.query_job(job_id)
                job_bill_state = \
                    JobBillingStatement.objects.filter(job_id=job_id)
                total_runtime = job_bill_state.aggregate(
                    total_runtime=Sum('billing_runtime'))['total_runtime'] \
                    if job_bill_state else 0
                billing_runtime = job['runtime'] - total_runtime
                if not job_bill_state.exists() or billing_runtime > 0:
                    charge_job(job)
                    charge_jobs.append(job_id)
                    tmp_stdout_jobids["charged_jobs_count"] += 1
                else:
                    logger.info(
                        "Job was already charged. "
                        "Job id: %d, Scheduler id: %s",
                        job["id"], job["identity_str"]
                    )
                    tmp_stdout_jobids["already_charged_jobs_count"] += \
                        job_bill_state.count()
            except UserBillGroupNotExistException:
                tmp_stdout_jobids["no_user_billing_mapping_count"] += 1
            except Exception:
                print_red("Charge job failed. Scheduler id: {}".format(job_id))
                tmp_stdout_jobids["failed_charged_jobs_count"] += 1

            if sum(tmp_stdout_jobids.values()) > 500:
                tmp_stdout_jobids["time"] = datetime.now()
                print(tmp_stdout_msg.format(**tmp_stdout_jobids))
                tmp_stdout_jobids = {
                    "already_charged_jobs_count": 0,
                    "charged_jobs_count": 0,
                    "no_user_billing_mapping_count": 0,
                    "failed_charged_jobs_count": 0
                }

        if sum(tmp_stdout_jobids.values()) > 0:
            tmp_stdout_jobids["time"] = datetime.now()
            print(tmp_stdout_msg.format(**tmp_stdout_jobids))

        if not charge_jobs:
            msg = 'No jobs need to be charged.'
        else:
            msg = "Charge all jobs finished."
        logging.info(msg)
        print_green(msg)

    @classmethod
    def _sync_storage_billing_statement(cls, start_time, end_time):
        day_count = (end_time - start_time).days + 1
        for day in range(day_count):
            bill_date = start_time + timedelta(days=day)
            try:
                billing_user = StorageBilling().billing(
                    bill_date)
                if billing_user:
                    print_green(
                        "Synchronize {0:%Y-%m-%d}'s storage billing statement."
                        " User:{1}".format(bill_date, ','.join(billing_user)))
                else:
                    print_green("The {:%Y-%m-%d}'s storage was already "
                                "charged".format(bill_date))
            except CalledProcessError:
                msg = "Currently, GPFS is the only file system supported " \
                      "by storage billing. \nIf you are using a GPFS " \
                      "system, check whether GPFS is installed correctly"
                print_red(msg)
                logger.warning(msg)
                return
            except Exception as e:
                print_red("Failed to sync storage billing statement. \n"
                          "{}".format(e))
                return

        msg = "Charge storage finished."
        logging.info(msg)
        print_green(msg)

    @classmethod
    def _get_charged_job_id(cls, starttime, endtime):
        billstates = JobBillingStatement.objects.filter(
            job_start_time__gte=starttime,
            job_end_time__lte=endtime
        )
        charged_job_ids = [
            billstate.job_id for billstate in billstates
        ]
        return charged_job_ids
