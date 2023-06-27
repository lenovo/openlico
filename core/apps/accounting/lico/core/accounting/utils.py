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
import csv
import logging
import re
from datetime import timedelta

from dateutil.tz import tzoffset
from django.conf import settings
from django.utils.translation import trans_real, ugettext

from lico.core.contrib.client import Client

from .exceptions import (
    InvalidMinuteChargeRateException, MissingMinuteChargeRateException,
)
from .models import Discount, Gresource

logger = logging.getLogger(__name__)


def handle_gres_charge_rate(data):
    if data['gcr_display_type']:
        for gres in data['gcr_display_type']:
            if data['gcr_display_type'][gres] == 'hour':
                crh = data['gres_charge_rate'][gres]
                data['gres_charge_rate'][gres] = round(crh, 4)
                if 'gcr_minute' not in data:
                    data['gcr_minute'] = {}
                data['gcr_minute'].update({gres: 0.0})
            else:  # minute
                if 'gcr_minute' not in data or gres not in data['gcr_minute']:
                    logger.error("Gres minute charge rate must be set.")
                    raise MissingMinuteChargeRateException
                crm = data['gcr_minute'][gres]
                if crm is None or crm < 0:
                    logger.error("The value of gcr_minute['%s'] must be a "
                                 "number greater than or equal to 0", gres)
                    raise InvalidMinuteChargeRateException
                data['gcr_minute'][gres] = round(crm, 4)
                data['gres_charge_rate'][gres] = round(crm * 60, 4)
        return data


def handle_resource_charge_rate(data):
    charge_rate_minute_mapping = {
        "mcr_display_type": ["mcr_minute", "memory_charge_rate"],
        "cr_display_type": ["cr_minute", "charge_rate"]
    }
    for dt in charge_rate_minute_mapping:
        if data[dt] == "hour":
            data[charge_rate_minute_mapping[dt][0]] = 0.0
        else:  # minute
            crm = charge_rate_minute_mapping[dt][0]
            if crm not in data:
                logger.error("%s must be in request.data", crm)
                raise MissingMinuteChargeRateException
            if data[crm] is None or data[crm] < 0:
                logger.error(
                    "The value of %s must be a number "
                    "greater than or equal to 0 ", crm
                )
                raise InvalidMinuteChargeRateException
            data[charge_rate_minute_mapping[dt][1]] = round(data[crm] * 60, 4)
    return data


def handle_request_data(data):
    handle_gres_charge_rate(data)
    handle_resource_charge_rate(data)
    processed_data = {
        'gres_charge_rate': data['gres_charge_rate'],
        'gcr_minute': data['gcr_minute'],
        'gcr_display_type': data['gcr_display_type'],
        'cr_minute': round(data['cr_minute'], 4),
        'charge_rate': round(data['charge_rate'], 4),
        'mcr_minute': round(data['mcr_minute'], 4),
        'memory_charge_rate': round(data['memory_charge_rate'], 4)
    }
    data.update(processed_data)
    return data


def red_string(string):
    return '\033[31m{}\033[0m'.format(string)


def read_csvfile():
    csv_path = settings.ACCOUNTING.GRES_FILE

    gres_list = []
    title = ['code', 'display_name', 'unit']
    with open(csv_path, "r")as f:
        gres = [gre for gre in csv.reader(
            line.strip() for line in f
            if not re.match(r'^[\"\']?\s*#', line.strip())) if gre
        ]
        if not gres:
            return []
        elif gres[0] != title:
            raise SystemExit(
                'Find invalid title lines in {0}:\n{1}\n'.format(
                    csv_path, red_string(gres[0]))
            )
        for gre in gres[1:]:
            if len(gre) != len(title):
                raise SystemExit(
                    'Find invalid resource lines in {0}:\n{1}\n'.format(
                        csv_path, red_string(gre))
                )
            for gr in gre:
                if not re.match(r'^[\w\:]+$', gr.strip()):
                    raise SystemExit(
                        'Find invalid resource lines in {0}:\n{1}\n'.format(
                            csv_path, red_string(gre))
                    )
            gres_list.append({
                'code': gre[0],
                'display_name': gre[1],
                'unit': gre[2]
            })
        return gres_list


def sync_table():
    gres_list = read_csvfile()
    for gres in gres_list:
        Gresource.objects.update_or_create(
            code=gres['code'],
            billing=(":" not in gres['code']),
            defaults=gres
        )


def get_gresource_codes(billing=True):
    gres_obj = Gresource.objects
    if billing:
        gres_obj = gres_obj.filter(billing=True)
    gres_obj = gres_obj.order_by('id')
    return [gres.code for gres in gres_obj]


def get_user_discount(username):
    user_discount = Discount.objects.filter(
        type=Discount.USER, name=username).first()
    if user_discount is not None:
        return float(user_discount.discount)
    else:
        user_passwd = Client().auth_client().fetch_passwd(
            username=username
        )
        gr_name = user_passwd.group.name
        if gr_name is not None:
            usergroup_discount = Discount.objects.filter(
                type=Discount.USERGROUP, name=gr_name).first()
            return float(usergroup_discount.discount) \
                if usergroup_discount is not None else 1.0
        else:
            return 1.0


def get_local_timezone():
    return tzoffset(
        'lico/local',
        timedelta(
            minutes=1
        ) * settings.ACCOUNTING.BILLING.TIMEZONE_OFFSET
    )


def set_language(language):
    back_language = dict(settings.LANGUAGES)
    if language not in back_language:
        language = settings.LANGUAGE_CODE
    trans_real.activate(language)


billing_type_translate_code = {
    'job': 'Deposit.Type.Job',
    'storage': 'Deposit.Type.Storage',
    'deposit': 'Deposit.Type.Deposit',
    'withdraw': 'Deposit.Type.Withdraw',
}


def trans_billing_type(billing_type):
    trans_code = billing_type_translate_code[billing_type]
    return ugettext(trans_code)
