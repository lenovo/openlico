# -*- coding: utf-8 -*-
# Copyright 2020-present Lenovo
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
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timedelta
from functools import reduce

from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.db.models import (
    DateTimeField, ExpressionWrapper, F, FloatField, Sum,
)
from django.utils.translation import trans_real
from rest_framework.views import APIView

from lico.core.contrib.client import Client

from ..models import BillingFile, JobBillingStatement, StorageBillingStatement
from ..utils import get_gresource_codes, get_local_timezone
from .billing_export import BillingReportExport
from .etc import GRES

logger = logging.getLogger(__name__)

GRES_CODES = get_gresource_codes()
CONTEXT = {
        'doctype': "xls",
        'start_time': None,
        'end_time': None,
        'data': None,
        'job_data': [],
        'storage_data': [],
        'username': '',
        'billgroup': '',
        'gres': GRES,
        'bill_name': ''
    }


def get_bill_cycle(localtime, cycle_type='daily'):
    if 'daily' == cycle_type:
        yesterday = localtime - timedelta(days=1)
        start_time = yesterday.replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        end_time = localtime.replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        return start_time, end_time
    elif 'monthly' == cycle_type:
        last_month = localtime - relativedelta(months=1)
        start_time = last_month.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        end_time = localtime.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        return start_time, end_time
    else:
        pass


def get_billgroup_name(start_time, end_time, username):
    job_billings = JobBillingStatement.objects.filter(
        create_time__gte=start_time,
        create_time__lt=end_time,
        submitter=username
    )
    storage_billings = StorageBillingStatement.objects.filter(
        create_time__gte=start_time,
        create_time__lt=end_time,
        username=username
    )
    create_time = None
    billgroup_name = ''
    if job_billings.count() > 0:
        job_billing = job_billings.latest('create_time')
        create_time = job_billing.create_time
        billgroup_name = job_billing.bill_group_name
    if storage_billings.count() > 0:
        storage_billing = storage_billings.latest('create_time')
        if create_time is None or create_time < storage_billing.create_time:
            billgroup_name = storage_billing.bill_group_name
    if not billgroup_name:
        user_bill_group_list = Client().accounting_client(
        ).get_user_bill_group_mapping(
            [username]
        )
        if not user_bill_group_list:
            logger.warning(
                '%s does not belong to any billing group', username
            )
        else:
            billgroup_name = user_bill_group_list[0].bill_group_name
    return billgroup_name


def sum_gres(gres_counts: dict, gres_costs: dict, runtime: int):
    gres_count_dict = dict(zip(GRES_CODES, [0]*len(GRES_CODES)))
    gres_cost_dict = dict(zip(GRES_CODES, [0]*len(GRES_CODES)))

    for gres_code in set(list(gres_costs.keys()) + list(gres_counts.keys())):
        code = gres_code.split('/')[0]
        if code in gres_count_dict:
            gres_count_dict[code] += \
                gres_counts.get(gres_code, 0) * runtime / 3600.0
        if code in gres_cost_dict:
            gres_cost_dict[code] += gres_costs.get(gres_code, 0)
    return gres_count_dict, gres_cost_dict


def sum_counter_to_dict(src_counter, add_counter):

    target_counter = dict(src_counter)
    if src_counter + add_counter:
        target_counter.update(dict(src_counter + add_counter))

    return target_counter


def _query_job_billing(start_time, end_time, username=None):
    query_job = JobBillingStatement.objects.filter(
        create_time__gte=start_time,
        create_time__lt=end_time
    )
    if username:
        query_job = query_job.filter(submitter=username)
    tmp_values = query_job.annotate(
        date=ExpressionWrapper(
            F('create_time'), output_field=DateTimeField()),
        core_time=ExpressionWrapper(
            F("cpu_count") * F("billing_runtime"), output_field=FloatField()
        ),
        mem_time=ExpressionWrapper(
            F("memory_count") * F("billing_runtime"), output_field=FloatField()
        )
    ).values("date", "submitter", "job_id").\
        annotate(
            cpu_count=Sum('core_time')/3600.0,
            cpu_cost=Sum("cpu_cost"),
            memory_count=Sum('mem_time')/3600.0,
            memory_cost=Sum("memory_cost"),
            billing_cost=Sum("billing_cost"),
            billing_runtime=Sum('billing_runtime')
        ).values(
        "date", "submitter", "cpu_count", "cpu_cost", "memory_count",
        "memory_cost", "billing_cost", "billing_runtime", "job_id",
        "gres_count", "gres_cost"
    )

    for value in tmp_values:
        """
        gres_cost/gres_count:
        {
            'gpu': 10, 'fpga': 10
        }
        """
        gres_count, gres_cost = sum_gres(
            value['gres_count'], value['gres_cost'], value['billing_runtime'])

        for code in GRES_CODES:
            key = 'gres_{0}'.format(code)
            value[key] = {
                'count': gres_count.get(code, 0.0),
                'cost': gres_cost.get(code, 0.0)
            }
    return tmp_values


def _query_storage_billing(start_time, end_time, username=None):
    query_s = StorageBillingStatement.objects.filter(
        billing_date__gte=start_time,
        billing_date__lt=end_time
    )
    if username:
        query_s = query_s.filter(username=username)
    query_s = query_s.annotate(date=ExpressionWrapper(
        F('billing_date'),
        output_field=DateTimeField())) \
        .values("date") \
        .annotate(storage_count=Sum("storage_count"),
                  storage_cost=Sum("storage_cost"),
                  billing_cost=Sum("billing_cost")
                  )
    return query_s


def _billing_statistics_data(users, data):
    tmp_values = _query_job_billing(data['start_time'], data['end_time'])
    for username in users:
        user_data = OrderedDict()
        storage_count, storage_cost, storage_billing_cost = 0, 0, 0
        query_s = _query_storage_billing(
            data['start_time'], data['end_time'], username)
        for q in query_s:
            storage_count += q['storage_count']
            storage_cost += q['storage_cost']
            storage_billing_cost += q['billing_cost']
        set_job_id = set()
        user_data['username'] = username
        user_data['jobcounts'] = 0
        user_data['runtime'] = 0
        user_data['storage_count'] = storage_count
        user_data['storage_cost'] = storage_cost
        user_data['cpu_count'] = 0
        user_data['cpu_cost'] = 0
        user_data['memory_count'] = 0
        user_data['memory_cost'] = 0
        for code in GRES_CODES:
            key = 'gres_{0}'.format(code)
            user_data[key] = {
                'count': 0.0,
                'cost': 0.0
            }
        user_data['total'] = storage_cost
        user_data['actual_total'] = storage_billing_cost
        data['actual_total_cost'] += storage_billing_cost

        for tmp_value in tmp_values:
            if username == tmp_value["submitter"]:
                set_job_id.add(tmp_value['job_id'])
                user_data['runtime'] += tmp_value['billing_runtime']
                user_data['memory_count'] += tmp_value['memory_count']
                user_data['memory_cost'] += tmp_value['memory_cost']
                user_data['cpu_count'] += tmp_value['cpu_count']
                user_data['cpu_cost'] += tmp_value['cpu_cost']

                tmp_gres_cost = 0.0
                for code in GRES_CODES:
                    key = 'gres_{0}'.format(code)
                    user_gres = Counter(user_data[key])
                    tmp_gres = Counter(tmp_value[key])
                    user_data[key] = sum_counter_to_dict(user_gres, tmp_gres)
                    tmp_gres_cost += tmp_value[key].get('cost', 0.0)

                user_data['total'] += tmp_value['cpu_cost'] + \
                    tmp_value['memory_cost'] + tmp_gres_cost
                user_data['actual_total'] += tmp_value['billing_cost']
                data['actual_total_cost'] += tmp_value['billing_cost']
        user_data['jobcounts'] = len(set_job_id)
        data['data'].append(user_data)
    data['start_time'] = data['start_time']
    data['end_time'] = data['end_time']
    return data


def _billing_detail_data(data):
    job_obj = JobBillingStatement.objects.filter(
            create_time__gte=data['start_time'],
            create_time__lt=data['end_time'],
            submitter=data['username'])
    for job in job_obj.iterator():
        job_data = OrderedDict()
        job_data['record_id'] = job.record_id
        job_data['job_id_name'] = job.scheduler_id+'/'+job.job_name
        job_data['queue'] = job.queue
        job_data['billing_time'] = job.billing_runtime
        job_data['charge_rate'] = job.charge_rate
        job_data['cpu_count'] = job.cpu_count
        job_data['cpu_cost'] = job.cpu_cost
        job_data['memory_charge_rate'] = job.memory_charge_rate
        job_data['memory_count'] = job.memory_count
        job_data['memory_cost'] = job.memory_cost
        gres_charge_rate = job.gres_charge_rate
        gres_count = job.gres_count
        gres_cost = job.gres_cost
        for code in GRES_CODES:
            count = 0.0
            for gpu_type, value in gres_count.items():
                if gpu_type.split('/')[0] == code:
                    count += value
            key = 'gres_{0}'.format(code)
            job_data[key] = {
                'charge_rate': gres_charge_rate.get(code, 0.0),
                'count': count,
                'cost': gres_cost.get(code, 0.0)
            }
        job_data['row_total_cost'] = \
            job_data['cpu_cost'] + job_data['memory_cost'] + \
            sum(gres_cost.values())

        job_data['discount'] = job.discount
        job_data['job_actual_cost'] = job.billing_cost
        data['actual_total_cost'] += job.billing_cost
        data['job_data'].append(job_data)


def query_user_daily(username, start_time, end_time, bill_date):
    data = dict()
    data['username'] = username
    data['billgroup'] = get_billgroup_name(start_time, end_time, username)
    data['create_time'] = datetime.now(tz=get_local_timezone())
    data['bill_date'] = bill_date
    data['actual_total_cost'] = 0
    data['storage_data'] = []
    data['job_data'] = []
    data['bill_name'] = 'User_Daily_Bills'
    data['start_time'], data['end_time'] = start_time, end_time
    for storage in StorageBillingStatement.objects.filter(
            billing_date__gte=data['start_time'],
            billing_date__lt=data['end_time'],
            username=data['username']).iterator():
        storage_data = OrderedDict()
        storage_data['path'] = storage.path
        storage_data['storage_capacity'] = storage.storage_capacity
        storage_data['storage_charge_rate'] = \
            storage.storage_charge_rate
        storage_data['storage_count'] = storage.storage_count
        storage_data['storage_cost'] = storage.storage_cost
        storage_data['row_total_cost'] = storage_data['storage_cost']
        storage_data['discount'] = storage.discount
        storage_data['actual_total'] = storage.billing_cost
        data['actual_total_cost'] += storage_data['actual_total']
        data['storage_data'].append(storage_data)
    _billing_detail_data(data)
    CONTEXT.update(data)
    exporter = BillingReportExport
    filename = exporter(**CONTEXT).report_export()
    BillingFile.objects.update_or_create(
        billing_type='user',
        period='daily',
        billing_date=datetime.date(data['bill_date']),
        username=username,
        defaults=dict(filename=filename),
    )
    logger.info(
        "Generate user_daily_report report successful! "
        "username is %s, day is %s",
        username,
        data['bill_date'].astimezone(
            tz=get_local_timezone()
        ).strftime('%Y-%m-%d')
    )


def query_admin_daily(start_time, end_time, bill_date):
    data = dict()
    data['username'] = ''
    data['data'] = []
    data['create_time'] = datetime.now(tz=get_local_timezone())
    data['bill_date'] = bill_date
    data['actual_total_cost'] = 0
    data['bill_name'] = 'Daily_Summary_Bills'
    data['start_time'], data['end_time'] = start_time, end_time
    tmp_values = _query_job_billing(data['start_time'], data['end_time'])

    for username in _get_user_range(start_time, end_time):
        user_data = OrderedDict()
        set_job_id = set()
        user_data['username'] = username
        user_data['billgroup'] = get_billgroup_name(
            start_time, end_time, username
        )
        user_data['jobcounts'] = 0
        user_data['runtime'] = 0
        query_s = _query_storage_billing(
            data['start_time'], data['end_time'], username)
        storage_count = query_s[0]['storage_count'] \
            if query_s.count() > 0 else 0
        storage_cost = query_s[0]['storage_cost'] \
            if query_s.count() > 0 else 0
        user_data['storage_count'] = storage_count
        user_data['storage_cost'] = storage_cost
        user_data['cpu_count'] = 0
        user_data['cpu_cost'] = 0
        user_data['memory_count'] = 0
        user_data['memory_cost'] = 0
        for code in GRES_CODES:
            key = 'gres_{0}'.format(code)
            user_data[key] = {
                'count': 0.0,
                'cost': 0.0
            }
        user_data['total'] = storage_cost
        storage_actual_total = query_s[0]['billing_cost'] \
            if query_s.count() > 0 else 0
        user_data['actual_total'] = storage_actual_total
        data['actual_total_cost'] += user_data['actual_total']
        for tmp_value in tmp_values:
            if username == tmp_value["submitter"]:
                set_job_id.add(tmp_value['job_id'])
                user_data['runtime'] += tmp_value['billing_runtime']
                user_data['cpu_count'] += tmp_value['cpu_count']
                user_data['cpu_cost'] += tmp_value['cpu_cost']
                user_data['memory_count'] += tmp_value['memory_count']
                user_data['memory_cost'] += tmp_value['memory_cost']
                # Add Gres Count and Cost
                tmp_gres_cost = 0.0
                for code in GRES_CODES:
                    key = 'gres_{0}'.format(code)
                    user_gres = Counter(user_data[key])
                    tmp_gres = Counter(tmp_value[key])
                    user_data[key] = sum_counter_to_dict(user_gres, tmp_gres)
                    tmp_gres_cost += tmp_value[key].get('cost', 0.0)

                user_data['actual_total'] += tmp_value['billing_cost']
                user_data['total'] += tmp_value['cpu_cost'] + \
                    tmp_value['memory_cost']+tmp_gres_cost
                data['actual_total_cost'] += tmp_value['billing_cost']
        user_data['jobcounts'] = len(set_job_id)

        data['data'].append(user_data)

    CONTEXT.update(data)
    exporter = BillingReportExport
    filename = exporter(**CONTEXT).report_export()
    BillingFile.objects.update_or_create(
        billing_type='cluster',
        period='daily',
        billing_date=datetime.date(data['bill_date']),
        defaults=dict(filename=filename)
    )
    logger.info(
        "Generate admin_daily_report report successful! Date is %s",
        data['bill_date'].astimezone(
            tz=get_local_timezone()
        ).strftime('%Y-%m-%d')
    )


def query_user_month(username, start_time, end_time, bill_month):
    data = dict()
    data['username'] = username
    data['billgroup'] = get_billgroup_name(start_time, end_time, username)
    data['create_time'] = datetime.now(tz=get_local_timezone())
    data['bill_date'] = bill_month
    data['bill_name'] = 'User_Monthly_Bills'
    data['actual_total_cost'] = 0
    data['start_time'], data['end_time'] = start_time, end_time
    data['data'] = []
    query_s = _query_storage_billing(
            data['start_time'], data['end_time'], data['username'])
    tmp_values = _query_job_billing(
        data['start_time'], data['end_time'], data['username'])

    """
    datas for example
    {
        '2023.02.08': [{"billing_date": "2023.02.08", "storage_cost": 0, ...}],
        '2023.02.09': [{"billing_date": "2023.02.09", "storage_cost": 0, ...}]
    }
    """
    datas = {}
    set_jobs_id = defaultdict(set)
    for tmp_value in tmp_values:
        billing_date = tmp_value['date'].astimezone(
            tz=get_local_timezone()
        ).strftime('%Y-%m-%d')
        if billing_date not in datas:
            datas[billing_date] = []
            user_data = OrderedDict()
            user_data['billing_date'] = billing_date
            user_data['billgroup'] = data['billgroup']
            user_data['jobcounts'] = 0
            user_data['runtime'] = tmp_value['billing_runtime']
            user_data['storage_count'] = 0
            user_data['storage_cost'] = 0
            user_data['cpu_count'] = tmp_value['cpu_count']
            user_data['cpu_cost'] = tmp_value['cpu_cost']
            user_data['memory_count'] = tmp_value['memory_count']
            user_data['memory_cost'] = tmp_value['memory_cost']
            tmp_gres_cost = 0.0
            for code in GRES_CODES:
                key = 'gres_{0}'.format(code)
                user_data[key] = tmp_value[key]
                tmp_gres_cost += tmp_value[key].get('cost', 0.0)

            user_data['total'] = user_data['cpu_cost'] + \
                user_data['memory_cost'] + tmp_gres_cost
            user_data['actual_total'] = tmp_value['billing_cost']
            data['actual_total_cost'] += user_data['actual_total']
            datas[billing_date].append(user_data)
        else:
            datas[billing_date][0]['runtime'] += tmp_value['billing_runtime']
            datas[billing_date][0]['cpu_count'] += tmp_value['cpu_count']
            datas[billing_date][0]['cpu_cost'] += tmp_value['cpu_cost']
            datas[billing_date][0]['memory_count'] += tmp_value['memory_count']
            datas[billing_date][0]['memory_cost'] += tmp_value['memory_cost']

            tmp_gres_cost = 0.0
            for code in GRES_CODES:
                key = 'gres_{0}'.format(code)
                date_gres = Counter(datas[billing_date][0][key])
                tmp_gres = Counter(tmp_value[key])
                datas[billing_date][0][key] = sum_counter_to_dict(
                    date_gres, tmp_gres
                )
                tmp_gres_cost += tmp_value[key].get('cost', 0.0)

            datas[billing_date][0]['total'] += tmp_value['cpu_cost'] + \
                tmp_value['memory_cost'] + tmp_gres_cost
            datas[billing_date][0]['actual_total'] += tmp_value['billing_cost']
            data['actual_total_cost'] += tmp_value['billing_cost']

        if tmp_value['job_id'] not in set_jobs_id[billing_date]:
            datas[billing_date][0]['jobcounts'] += 1
            set_jobs_id[billing_date].add(tmp_value['job_id'])

    # job storage billing for user month bills
    for storage in query_s:
        billing_date = storage['date'].astimezone(
            tz=get_local_timezone()
        ).strftime('%Y-%m-%d')
        if billing_date not in datas:
            datas[billing_date] = []
            storage_data = OrderedDict()
            storage_data['billing_date'] = billing_date
            storage_data['billgroup'] = data['billgroup']
            storage_data['jobcounts'] = 0
            storage_data['runtime'] = 0
            storage_data['storage_count'] = storage['storage_count']
            storage_data['storage_cost'] = storage['storage_cost']
            storage_data['cpu_count'] = 0
            storage_data['cpu_cost'] = 0
            storage_data['memory_count'] = 0
            storage_data['memory_cost'] = 0
            for code in GRES_CODES:
                key = 'gres_{0}'.format(code)
                storage_data[key] = {
                    'count': 0.0,
                    'cost': 0.0
                }
            storage_data['total'] = storage['storage_cost']
            storage_data['actual_total'] = storage['billing_cost']
            data['actual_total_cost'] += storage['billing_cost']
            datas[billing_date].append(storage_data)
        else:
            datas[billing_date][0]['storage_count'] += \
                storage['storage_count']
            datas[billing_date][0]['storage_cost'] += \
                storage['storage_cost']
            datas[billing_date][0]['total'] += \
                storage['storage_cost']
            # row for he ji
            datas[billing_date][0]['actual_total'] += \
                storage['billing_cost']
            data['actual_total_cost'] += storage['billing_cost']

    datas = datas.values() if len(datas.values()) > 0 else [[]]
    data['data'] = reduce(lambda x, y: x+y, datas)
    data['start_time'] = data['start_time']
    data['end_time'] = data['end_time']
    CONTEXT.update(data)
    exporter = BillingReportExport
    filename = exporter(**CONTEXT).report_export()
    BillingFile.objects.update_or_create(
        billing_type='user',
        period='monthly',
        username=username,
        billing_date=datetime.date(data['bill_date']),
        defaults=dict(filename=filename)
    )
    logger.info(
        "Generate user_month_report report successful! username is %s,"
        "month is %s", username, data['bill_date'].astimezone(
            tz=get_local_timezone()
        ).strftime('%Y-%m')
    )


def query_admin_month(users, start_time, end_time, bill_month):
    data = dict()
    data['data'] = []
    data['username'] = ''
    data['create_time'] = datetime.now(tz=get_local_timezone())
    data['bill_date'] = bill_month
    data['actual_total_cost'] = 0
    data['start_time'], data['end_time'] = start_time, end_time
    data['bill_name'] = 'Monthly_Summary_Bills'
    data = _billing_statistics_data(users, data)
    CONTEXT.update(data)
    exporter = BillingReportExport
    filename = exporter(**CONTEXT).report_export()
    BillingFile.objects.update_or_create(
        billing_type='cluster',
        period='monthly',
        billing_date=datetime.date(data['bill_date']),
        defaults=dict(filename=filename)
    )
    logger.info(
        "Generate admin_month_report report successful! Month is %s",
        data['bill_date'].astimezone(
            tz=get_local_timezone()
        ).strftime('%Y-%m')
    )


def _get_user_range(start_time, end_time):
    user_objects = Client().user_client().get_user_list()
    usernames = [user_obj.username for user_obj in user_objects]
    job_submitters = JobBillingStatement.objects.filter(
        create_time__gte=start_time,
        create_time__lt=end_time
    ).values_list('submitter')
    job_usernames = [submitter[0] for submitter in job_submitters]

    storage_users = StorageBillingStatement.objects.filter(
        create_time__gte=start_time,
        create_time__lt=end_time
    ).values_list('username')
    storage_usernames = [submitter[0] for submitter in storage_users]

    # Return value format: set --> {user1, user2, user3}
    return set(usernames).union(job_usernames, storage_usernames)


def _query_user_daily(localtime):
    start_time, end_time = get_bill_cycle(localtime, 'daily')
    bill_date = localtime - timedelta(days=1)
    for username in _get_user_range(start_time, end_time):
        query_user_daily(username, start_time, end_time, bill_date)


def _query_admin_daily(localtime):
    start_time, end_time = get_bill_cycle(localtime, 'daily')
    bill_date = localtime - timedelta(days=1)
    query_admin_daily(start_time, end_time, bill_date)


def _query_user_month(localtime):
    start_time, end_time = get_bill_cycle(localtime, 'monthly')
    bill_month = start_time
    for username in _get_user_range(start_time, end_time):
        query_user_month(username, start_time, end_time, bill_month)


def _query_admin_month(localtime):
    start_time, end_time = get_bill_cycle(localtime, 'monthly')
    bill_month = start_time
    users = _get_user_range(start_time, end_time)
    query_admin_month(users, start_time, end_time, bill_month)


class BillGroupReportView(APIView):
    config = {
        'user_daily_report': (_query_user_daily, BillingReportExport),
        'admin_daily_report': (_query_admin_daily, BillingReportExport),
        'user_month_report': (_query_user_month, BillingReportExport),
        'admin_month_report': (_query_admin_month, BillingReportExport),
    }

    def save_report(self, target, localtime):
        language = settings.ACCOUNTING.BILLING.LANGUAGE
        trans_real.activate(language.lower())
        action, exporter = self.config.get(
            target, (None, BillingReportExport))
        try:
            action(localtime)
        except Exception:
            logger.exception("Generate %s report failed", target)
            raise

        return True
