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
import time
from collections import Counter
from datetime import timedelta

from dateutil.tz import tzoffset

from lico.core.contrib.client import Client

from .exceptions import JobOperationException
from .helpers.scheduler_helper import get_admin_scheduler, get_scheduler


def get_users_from_bill_ids(bills):
    if not bills:
        return []
    return get_users_from_filter(
        {
            'value_type': 'billinggroup',
            'values': bills
        }
    )


def get_bg_names_from_data(bills):
    if not bills:
        return []
    try:
        all_bill_group = Client().accounting_client().get_bill_group_list()
        bg_dict = {bg.id: bg.name for bg in all_bill_group}
        if bills:
            return [bg_dict[bill_id] for bill_id in bills]
        return bg_dict.values()
    except Exception:
        return []


# On host version, gres can be define by customer.
def get_gres_codes():
    gres_codes = [gres.code for gres in
                  Client().accounting_client().get_gresource_codes()]
    return gres_codes


def get_user_bill_group_mapping():
    try:
        mapping = Client().accounting_client().get_user_bill_group_mapping()
        return {data.username: data.bill_group_name for data in mapping}
    except Exception:
        return {}


def get_users_from_filter(filter_, ignore_non_lico_user=True):  # noqa: C901
    value_type = filter_['value_type']
    values = filter_['values']

    if ignore_non_lico_user:
        # Handle "all"
        all_users = [user.username
                     for user in Client().user_client().get_user_list()]
        if not values:
            return all_users
        if value_type.lower() == 'username':
            return list(set([v.strip() for v in values]) & set(all_users))
    else:
        all_users = []
        if not values:
            return values
        if value_type.lower() == 'username':
            return values

    if value_type.lower() == 'usergroup':
        usernames = sum(
            (
                Client().user_client().get_group_user_list(group_name)
                for group_name in values
            ), []
        )

        return ['LICO-NOT-EXIST-USERNAME'] \
            if not usernames and bool(values) else usernames

    if value_type.lower() == 'billinggroup':
        try:
            res = Client().accounting_client().get_username_list(values)
        except Exception:
            return []

        usernames = sum(
            (bgu.username_list for bgu in res), []
        )

        return usernames if usernames else ['LICO-NOT-EXIST-USERNAME']

    return all_users


def convert_tres(tres: str) -> Counter:
    tres_counter = Counter()
    if not tres.strip():
        return tres_counter
    for res in tres.split(','):
        res_type, res_value = res.split(':')
        if res_type == "C":
            tres_counter["core_total_num"] += int(float(res_value))
        elif res_type.startswith("G/gpu"):
            tres_counter["gpu_total_num"] += float(res_value)
    return tres_counter


def get_timezone(timezone_offset: int):
    # PRC timezone_offset should be -480
    return tzoffset(
        'lico/local',
        timedelta(
            minutes=-timezone_offset
        )
    )


def get_available_queues(request, role=None):
    scheduler = get_admin_scheduler() \
        if role == 'admin' else get_scheduler(request.user)
    sched_queues = scheduler.query_available_queues()

    return sched_queues


def get_resource_num(tres, code):
    if not tres:
        return 0
    count = 0
    for tres_detail in tres.split(','):
        res_type, value = tres_detail.split(':')
        if code == 'cpu_cores' and res_type == 'C':
            count = int(float(value))
            break
        type_list = res_type.split('/')
        if code == 'gpu' and type_list[0] == 'G':
            count = int(float(value))
            break
    return count


def batch_status(target_nums, err_nums):
    # batch operation returned status
    if err_nums == 0:
        return "success"
    elif err_nums < target_nums:
        return "partial"
    else:
        raise JobOperationException


def get_display_runtime(runtime, start_time):
    if not start_time:
        return runtime
    return max([runtime, int(time.time()) - start_time])

