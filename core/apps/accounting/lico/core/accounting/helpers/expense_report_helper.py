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

import csv
import logging
from io import StringIO

from django.conf import settings
from django.utils.translation import ugettext as _

from ..models import Gresource
from .deposit_report_helper import format_datetime

logger = logging.getLogger(__name__)


class ExpenseReportExporter(object):
    def __init__(self, bill_query, doctype, timezone_offset):
        self.bill_query = bill_query
        self.report_export = getattr(self, 'export_' + doctype)
        self.timezone_offset = timezone_offset
        self.gres = Gresource.objects.filter(billing=True).order_by('id')

    def get_expense_report_head(self):
        expense_gres_heads = []
        for gres in self.gres:
            expense_gres_heads.append({
                'title': ["Django.accounting.expense_bill.GRES_Rate",
                          "Django.accounting.expense_bill.GRES_Used",
                          "Django.accounting.expense_bill.GRES_Cost"],
                'gres': gres.display_name,
                'g_unit': gres.unit
            })
        return [
            "Django.accounting.expense_bill.Date",
            "Django.accounting.expense_bill.Record_ID",
            "Django.accounting.expense_bill.Job_ID",
            "Django.accounting.expense_bill.Job_Name",
            "Django.accounting.expense_bill.User",
            "Django.accounting.expense_bill.Billing_Group",
            "Django.accounting.expense_bill.Queue",
            "Django.accounting.expense_bill.Run_Time",
            "Django.accounting.expense_bill.CPU_Rate",
            "Django.accounting.expense_bill.CPU_Used",
            "Django.accounting.expense_bill.CPU_Cost",
            "Django.accounting.expense_bill.Memory_Rate",
            "Django.accounting.expense_bill.Memory_Used",
            "Django.accounting.expense_bill.Memory_Cost",
            *expense_gres_heads,
            "Django.accounting.expense_bill.Sum_Total",
            "Django.accounting.expense_bill.Discount",
            "Django.accounting.expense_bill.Discounted_Cost"
        ]

    def gen_export_data(self):
        job_head = []
        job_data = []
        for head in self.get_expense_report_head():
            if isinstance(head, dict):
                job_head.extend([_(title).format(
                    unit=settings.ACCOUNTING.BILLING.UNIT,
                    g_unit=head['g_unit'],
                    gres=head['gres']) for title in head['title']])
            else:
                job_head.append(_(head).format(
                    unit=settings.ACCOUNTING.BILLING.UNIT))

        for bill in self.bill_query:
            gres_data = []
            gres_charge_rate = bill.gres_charge_rate
            gres_count = bill.gres_count
            gres_cost = bill.gres_cost
            for gres in self.gres:
                count = 0.0
                for gpu_type, value in gres_count.items():
                    if gpu_type.split('/')[0] == gres.code:
                        count += value
                gres_data.extend([
                    gres_charge_rate.get(gres.code, 0.0),
                    count,
                    gres_cost.get(gres.code, 0.0)
                ])
            job_data.append([
                format_datetime(
                    bill.create_time.astimezone(self.timezone_offset)),
                bill.record_id,
                bill.scheduler_id,
                bill.job_name,
                bill.submitter,
                bill.bill_group_name,
                bill.queue,
                bill.billing_runtime,
                bill.charge_rate,
                bill.cpu_count,
                bill.cpu_cost,
                bill.memory_charge_rate,
                bill.memory_count,
                bill.memory_cost,
                *gres_data,
                bill.cpu_cost + bill.memory_cost +
                sum(bill.gres_cost.values()),
                bill.discount,
                bill.billing_cost,
            ])
        return job_head, job_data

    def export_csv(self):
        job_head, job_data = self.gen_export_data()
        stream = StringIO()
        writer = csv.writer(stream)
        writer.writerow(job_head)
        writer.writerows(job_data)
        stream.seek(0)
        return stream, ".csv"
