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

import fcntl
import logging
import os
from collections import defaultdict
from datetime import datetime

from dateutil.tz import tzutc
from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.utils.timezone import now

from lico.core.job.helpers.scheduler_helper import (
    get_admin_scheduler, parse_job_identity,
)

from .exceptions import UserBillGroupNotExistException
from .models import (
    BillGroup, BillGroupQueuePolicy, Deposit, Gresource, JobBillingStatement,
    UserBillGroupMapping,
)
from .utils import get_user_discount

logger = logging.getLogger(__name__)

CORES = "C"
GRES = "G"
MEMORY = "M"


def _generate_record_id(job_id: str):
    # job_id length is 10 for record id
    format_job_id = job_id.zfill(10)[-10:]

    # time format for record id : 202302020734
    format_time = datetime.now().strftime("%Y%m%d%H%M%S")
    return format_time + format_job_id


def charge(count, seconds, rate):
    return round(
        count * seconds / 3600.0 * rate, 2
    )


def charge_job(job):
    lock_file_dir = settings.ACCOUNTING.BILLING.LOCK_FILE_DIR
    lock_file = os.path.join(lock_file_dir, 'charge_job.lock')
    with open(lock_file, 'w+') as lock_file_obj:
        fcntl.flock(lock_file_obj, fcntl.LOCK_EX)
        try:
            billgroup_user = UserBillGroupMapping.objects.get(
                username=job['submitter'])
        except UserBillGroupMapping.DoesNotExist:
            logger.exception(
                'the user: %s has not a bill group. Do not need to charge job.'
                'Job id: %d, Scheduler id: %s',
                job['submitter'], job['id'], job['scheduler_id']
            )
            raise UserBillGroupNotExistException

        billstatement = JobBillingStatement.objects.filter(job_id=job['id'])

        try:
            scheduler = get_admin_scheduler()
            job_list = scheduler.query_job(
                parse_job_identity(job["identity_str"]), include_history=True
            )
            job['runtime'] = get_job_all_runtime(job_list)
        except Exception as e:
            logger.exception(
                'Failed to query the historical running time of a job.'
                'Job id: %d, Scheduler id: %s, Reason: %s',
                job['id'], job['scheduler_id'], e)

        total_runtime = billstatement.aggregate(
            total_runtime=Sum('billing_runtime'))['total_runtime'] \
            if billstatement else 0
        actual_runtime = job['runtime'] - total_runtime
        if actual_runtime < 0:
            logger.exception(
                'The running time in the billing period is less than 0.'
                'Job id: %d, Scheduler id: %s, '
                'Charged Runtime: %s, Job Runtime: %s',
                job['id'], job['scheduler_id'], str(total_runtime),
                job['runtime']
            )
            return

        submitter_discount = get_user_discount(billgroup_user.username)

        charge_rate, gres_charge_rate, memory_charge_rate = get_charge_rate(
            billgroup_user.bill_group, job['queue']
        )

        tres_dict = _get_tres_dict(job)
        resource_dict = defaultdict(lambda: 0.0, tres_dict)

        cpu_cost = charge(
            resource_dict[CORES], actual_runtime, charge_rate
        )

        gres_charge_dict = defaultdict(lambda: 0.0, gres_charge_rate)
        gres_count_dict = defaultdict(lambda: 0.0, resource_dict[GRES])

        gres_cost = {}
        for gres in Gresource.objects.filter(billing=True).values_list(
                'code', flat=True):
            count = 0
            for gres_type, value in gres_count_dict.items():
                if gres == gres_type.split('/')[0]:
                    count += value
            gres_cost.update(
                {gres: charge(count, actual_runtime, gres_charge_dict[gres])}
            )

        memory_cost = charge(
            resource_dict[MEMORY], actual_runtime, memory_charge_rate
        )

        total_cost = round(cpu_cost + memory_cost + sum(gres_cost.values()), 2)
        billing_cost = round(total_cost * submitter_discount, 2)

        with transaction.atomic():
            bill_group = billgroup_user.bill_group
            record_id = _generate_record_id(str(job['id']))
            jobbillstatement = JobBillingStatement.objects.create(
                job_id=job['id'],
                job_name=job['job_name'],
                scheduler_id=job['scheduler_id'],
                submitter=job['submitter'],
                bill_group_id=bill_group.id,
                bill_group_name=bill_group.name,
                queue=job['queue'],
                job_create_time=datetime.fromtimestamp(
                    job['submit_time'], tz=tzutc()),
                job_start_time=datetime.fromtimestamp(
                    job['start_time'], tz=tzutc()),
                job_end_time=datetime.fromtimestamp(
                    job['end_time'], tz=tzutc()) if job['end_time'] else None,
                job_runtime=job['runtime'],
                charge_rate=charge_rate,
                cpu_count=resource_dict[CORES],
                cpu_cost=cpu_cost,
                gres_charge_rate=gres_charge_rate,
                gres_count=resource_dict[GRES],
                gres_cost=gres_cost,
                memory_charge_rate=memory_charge_rate,
                memory_count=resource_dict[MEMORY],
                memory_cost=memory_cost,
                discount=submitter_discount,
                total_cost=total_cost,
                billing_cost=billing_cost,
                billing_runtime=actual_runtime,
                record_id=record_id
            )

            bill_group = BillGroup.objects.select_for_update().get(
                id=bill_group.id
            )
            bill_group.balance = round(bill_group.balance-billing_cost, 2)
            bill_group.save()

            credits = -billing_cost
            Deposit.objects.create(
                user=job['submitter'],
                bill_group=bill_group,
                credits=credits,
                apply_time=jobbillstatement.create_time,
                approved_time=now(),
                billing_type=Deposit.BILLING_TYPE_CHOICES[1][0],
                billing_id=jobbillstatement.id,
                balance=bill_group.balance
            )
            logger.info("Job charged. Job id: %s, Scheduler id: %s",
                        job['id'], job['scheduler_id'])


def _get_tres_dict(job):
    tres_dict = {GRES: {}}
    if job['tres']:
        for i in job['tres'].split(','):
            key, value = i.split(':')
            if key.startswith('G/'):
                tres_dict[GRES][key.strip('G/')] = float(value)
            else:
                tres_dict[key] = float(value)
    return tres_dict


def get_charge_rate(bill_group, queue):
    bill_group_queues = BillGroupQueuePolicy.objects.order_by(
        '-last_operation_time').filter(bill_group_id=bill_group.id)
    for bill_group_queue in bill_group_queues:
        if queue in bill_group_queue.queue_list:
            charge_rate = bill_group_queue.charge_rate
            gres_charge_rate = bill_group_queue.gres_charge_rate
            memory_charge_rate = bill_group_queue.memory_charge_rate

            return charge_rate, gres_charge_rate, memory_charge_rate
    else:
        charge_rate = bill_group.charge_rate
        gres_charge_rate = bill_group.gres_charge_rate
        memory_charge_rate = bill_group.memory_charge_rate

        return charge_rate, gres_charge_rate, memory_charge_rate


def get_job_all_runtime(job_list):
    job_total_time = 0
    for job in job_list:
        job_total_time += job.runtime
    return job_total_time
