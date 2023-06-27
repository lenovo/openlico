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

import datetime
import logging
from io import BytesIO

from django.conf import settings
from django.template.loader import render_to_string
from django.utils.translation import ugettext
from weasyprint import HTML
from xlsxwriter import Workbook

from ..models import Deposit, JobBillingStatement, StorageBillingStatement
from ..utils import trans_billing_type

logger = logging.getLogger(__name__)

I18N = {
    "billing_group_details": {
        "head": [
            "Deposit.Record ID",
            "Deposit.Approved Time",
            "Deposit.Billing Type",
            "Deposit.Billing Description",
            "Deposit.User",
            "Deposit.Credits",
            "Deposit.Balance",
        ],
        "title": "Deposit.Billing Group"
    },
}


def format_datetime(date_time):
    if isinstance(date_time, int):
        date_time = datetime.datetime.fromtimestamp(date_time)
        return date_time.strftime("%F %T")
    if isinstance(date_time, str):
        date_time = datetime.datetime.strptime(
            date_time, "%Y-%m-%dT%H:%M:%S.%fZ")
        return date_time.strftime("%F %T")
    if isinstance(
            date_time, (datetime.datetime, datetime.date, datetime.time)):
        return date_time.strftime("%F %T")


def _counter(start=0, step=1):
    count = start
    while True:
        val = yield count
        count += step if val is None else val


class DepositReportExporter(object):
    creator_info_format = '{creator} {created_at} {create_time}'
    date_cycle_format = '{data_cycle} : {start_time} - {end_time}'

    def __init__(self, bill_group, doctype, start_time, end_time, creator,
                 create_time, template, filename, time_delta):
        self.data = self.query_deposit_then_format(
            bill_group, start_time, end_time, time_delta)
        self.bill_group = bill_group
        self.title = ugettext(I18N[filename].get('title')).format(
            billing_group=bill_group.name)
        self.headline = [
            ugettext(head).format(unit=settings.ACCOUNTING.BILLING.get('UNIT'))
            for head in I18N[filename].get('head')]
        self.report_export = getattr(self, 'export_' + doctype)
        self.start_time = start_time
        self.end_time = end_time
        self.creator = creator
        self.create_time = create_time
        self.template = template
        self.date_cycle = self.date_cycle_format.format(**{
            "data_cycle": ugettext('Deposit.Data Cycle'),
            "start_time": format_datetime(self.start_time),
            "end_time": format_datetime(self.end_time)
        })
        self.creator_info = self.creator_info_format.format(**{
            "creator": self.creator,
            "created_at": ugettext('Deposit.Created At'),
            "create_time": format_datetime(self.create_time)
        })

    @staticmethod
    def query_deposit_then_format(bill_group, start_time, end_time,
                                  time_delta):
        query_origin = Deposit.objects.filter(
            bill_group=bill_group,
            apply_time__range=[start_time, end_time]
        ).order_by('apply_time')
        result = list()
        for deposit in query_origin:
            if deposit.billing_type == 'job':
                job_state = JobBillingStatement.objects.get(
                    id=deposit.billing_id)
                deposit.billing_description = (
                    f'{job_state.scheduler_id} - {job_state.job_name}')
            elif deposit.billing_type == 'storage':
                storage_state = StorageBillingStatement.objects.get(
                    id=deposit.billing_id)
                deposit.billing_description = (
                    f'{storage_state.path}')
            else:
                if deposit.credits >= 0:
                    deposit.billing_type = 'deposit'
                else:
                    deposit.billing_type = 'withdraw'
                deposit.billing_description = '-'
            result.append([
                deposit.id,
                format_datetime(deposit.approved_time.astimezone(time_delta)),
                trans_billing_type(deposit.billing_type),
                deposit.billing_description,
                deposit.user,
                deposit.credits,
                deposit.balance,
            ])

        return iter(result)

    def _generate_html(self):
        return render_to_string(
            self.template,
            context={
                'title': self.title,
                'headline': self.headline,
                'data': self.data,
                'start_time': format_datetime(self.start_time),
                'end_time': format_datetime(self.end_time),
                'creator': self.creator,
                'create_time': format_datetime(self.create_time),
                'creator_info': self.creator_info,
                'date_cycle': self.date_cycle,
                'group_title': f'Billing Group: {self.bill_group.name}'
            }
        )

    def export_html(self):
        html = self._generate_html()
        return BytesIO(html.encode()), '.html'

    def export_pdf(self):
        stream = BytesIO()
        html = HTML(string=self._generate_html())
        html.write_pdf(stream)
        stream.seek(0)
        return stream, '.pdf'

    def export_xlsx(self):
        stream = BytesIO()
        excel_format = {
            'align': 'center',
            'bold': True,
            'valign': 'vcenter',
            'font_size': 10,
            'text_wrap': True,
            'font_name': 'Arial'
        }
        with Workbook(stream, dict(in_memory=True)) as book:
            sheet = book.add_worksheet(self.bill_group.name)
            counter = _counter()
            # write title
            excel_format.update({'font_size': 25, 'align': 'center'})
            title_merge_format = book.add_format(excel_format)
            sheet.merge_range(
                next(counter), counter.send(0), 0, len(self.headline) - 1,
                self.title,
                title_merge_format
            )

            # write create info
            excel_format.update({'font_size': 10, 'align': 'right'})
            info_merge_format = book.add_format(excel_format)
            sheet.merge_range(
                next(counter), 0, counter.send(1), len(self.headline) - 1,
                (self.creator_info + '\n' + self.date_cycle),
                info_merge_format
            )

            # write date table head
            excel_format.update({'align': 'center', 'text_wrap': False})
            head_merge_format = book.add_format(excel_format)
            next(counter)
            for colx, value in enumerate(self.headline, 0):
                sheet.write(
                    counter.send(0), colx, value, head_merge_format
                )
            # set frozen
            sheet.freeze_panes(4, 0)
            num_format = book.add_format({"num_format": "0.00"})
            # write table data
            for value in self.data:
                next(counter)
                for index, enum in enumerate(value):
                    if isinstance(enum, float):
                        sheet.write(counter.send(0), index, enum, num_format)
                    else:
                        sheet.write(counter.send(0), index, enum)

        stream.seek(0)
        return stream, '.xlsx'
