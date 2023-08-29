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
from datetime import datetime, timedelta

from dateutil import rrule
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.translation import trans_real
from six import print_

from ...models import BillingFile
from ...tasks.billing_statement import (
    _get_user_range, query_admin_daily, query_admin_month, query_user_daily,
    query_user_month,
)
from ...utils import get_local_timezone

logger = logging.getLogger(__name__)


def print_red(string):
    print('\033[31m{}\033[0m'.format(string))


def print_green(string):
    print('\033[92m{}\033[0m'.format(string))


class Command(BaseCommand):
    help = 'generate billing report'

    def add_arguments(self, parser):
        parser.add_argument(
            '-p', '--period', default='daily',
            choices=['daily', 'monthly'],
            help='Bill report period'
        )
        parser.add_argument(
            '-t', '--type', default='user',
            choices=['cluster', 'user'],
            help='Bill report type'
        )
        parser.add_argument(
            '-u', '--username', nargs='*', default='',
            help='This parameter is valid when type is user'
        )
        daily_group = parser.add_argument_group('Daily Options')
        monthly_group = parser.add_argument_group('Monthly Options')
        daily_group.add_argument(
            '--startdate',
            help='Bill report start date \n'
                 'Format: YYYY-MM-DD'
        )
        daily_group.add_argument(
            '--enddate',
            help='Bill report end date \n'
                 'Format: YYYY-MM-DD'
        )
        monthly_group.add_argument(
            '--startmonth',
            help='Bill report start month \n'
                 'Format: YYYY-MM'
        )
        monthly_group.add_argument(
            '--endmonth',
            help='Bill report end month \n'
                 'Format: YYYY-MM'
        )
        parser.add_argument(
            '-f', '--force',
            action='store_true',
            default=False,
            help='Force overwriting of existing bills'
        )

    def handle(self, *args, **options):
        language = settings.ACCOUNTING.BILLING.LANGUAGE
        trans_real.activate(language.lower())
        if options['type'] == 'user':
            if options['period'] == 'daily':
                self.user_daily_report(options)
            else:
                self.user_monthly_report(options)
        else:
            if options['period'] == 'daily':
                self.admin_daily_report(options)
            else:
                self.admin_monthy_report(options)

    @staticmethod
    def _generator_user_daily_report(
            bill_date, username, end_time, start_time, force):
        reports = BillingFile.objects.filter(
            billing_date=datetime.date(
                bill_date.astimezone(tz=get_local_timezone())
            ),
            username=username,
            billing_type=BillingFile.USER,
            period=BillingFile.DAILY,
        )
        if reports and not force:
            for report in reports:
                print_(
                    '{} already exits'.format(
                        report.filename
                    )
                )
            return
        query_user_daily(username, start_time, end_time, bill_date)
        print_(
            "Generate user daily report successfully! "
            "Username is {0}, date is {1:%Y-%m-%d}".format(
                username, bill_date))

    @staticmethod
    def _generator_user_month_report(
            bill_month, username, end_time, start_time, force
    ):
        reports = BillingFile.objects.filter(
            billing_date=datetime.date(
                bill_month.astimezone(tz=get_local_timezone())
            ),
            username=username,
            billing_type=BillingFile.USER,
            period=BillingFile.MONTHLY,
        )
        if reports and not force:
            for report in reports:
                print_(
                    '{} already exits'.format(
                        report.filename
                    )
                )
            return
        query_user_month(username, start_time, end_time, bill_month)
        print_(
            "Generate user month report successfully! "
            "Username is {0}, month is {1:%Y-%m}".format(
                username, bill_month))

    def generator_user_daily_report(self, dates, users=None, force=False):
        for date in dates:
            start_time, end_time = date
            bill_date = start_time
            user_range = _get_user_range(start_time, end_time)
            if users:
                intersection = set(users) & set(user_range)
                for username in intersection:
                    self._generator_user_daily_report(
                        bill_date, username, end_time, start_time, force)
                if set(users)-intersection:
                    print_red(
                        'User {0} not exists'.format(
                            ','.join(set(users)-intersection)
                        )
                    )
            else:
                for username in user_range:
                    self._generator_user_daily_report(
                        bill_date, username, end_time, start_time, force
                    )

    def generator_user_month_report(self, months, users=None, force=False):
        for month in months:
            start_time, end_time = month
            bill_month = start_time
            user_range = _get_user_range(start_time, end_time)
            if users:
                intersection = set(users) & set(user_range)
                for username in intersection:
                    self._generator_user_month_report(
                        bill_month, username, end_time, start_time, force)
                if set(users) - intersection:
                    print_red(
                        'User {0} not exists'.format(
                            ','.join(set(users) - intersection)
                        )
                    )
            else:
                for username in _get_user_range(start_time, end_time):
                    self._generator_user_month_report(
                        bill_month, username, end_time, start_time, force)

    @staticmethod
    def generator_admin_daily_report(dates, force=False):
        for date in dates:
            start_time, end_time = date
            bill_date = start_time
            reports = BillingFile.objects.filter(
                billing_date=datetime.date(
                    bill_date.astimezone(tz=get_local_timezone())
                ),
                billing_type=BillingFile.CLUSTER,
                period=BillingFile.DAILY,
            )
            if reports and not force:
                for report in reports:
                    print_(
                        '{} already exits'.format(
                            report.filename
                        )
                    )
                continue
            query_admin_daily(start_time, end_time, bill_date)
            print_(
                "Generate summary daily report successfully! "
                "Date is {0:%Y-%m-%d}".format(bill_date)
            )

    @staticmethod
    def generator_admin_month_report(months, force=False):
        for month in months:
            start_time, end_time = month
            bill_month = start_time
            usernames = _get_user_range(start_time, end_time)
            reports = BillingFile.objects.filter(
                billing_date=datetime.date(
                    bill_month.astimezone(tz=get_local_timezone())
                ),
                billing_type=BillingFile.CLUSTER,
                period=BillingFile.MONTHLY,
            )
            if reports and not force:
                for report in reports:
                    print_(
                        '{} already exits'.format(
                            report.filename
                        )
                    )
                continue
            query_admin_month(usernames, start_time, end_time, bill_month)
            print_(
                "Generate summary month report successfully! "
                "Month is {0:%Y-%m}".format(bill_month))

    def user_daily_report(self, options):
        if not options['startdate'] or not options['enddate']:
            raise SystemExit('Error: Billing date is empty!')

        dates = self.parse_daily_date(
            options['startdate'], options['enddate']
        )
        self.generator_user_daily_report(
            dates, options['username'], force=options['force']
        )

    def user_monthly_report(self, options):
        if not options['startmonth'] or not options['endmonth']:
            raise SystemExit('Error: Billing month is empty!')
        months = self.parse_month_date(
            options['startmonth'], options['endmonth']
        )
        self.generator_user_month_report(
            months, options['username'], force=options['force']
        )

    def admin_daily_report(self, options):
        if not options['startdate'] or not options['enddate']:
            raise SystemExit('Error: Billing date is empty!')
        dates = self.parse_daily_date(
            options['startdate'], options['enddate']
        )
        self.generator_admin_daily_report(dates, force=options['force'])

    def admin_monthy_report(self, options):
        if not options['startmonth'] or not options['endmonth']:
            raise SystemExit('Error: Billing month is empty!')
        months = self.parse_month_date(
            options['startmonth'], options['endmonth']
        )
        self.generator_admin_month_report(months, force=options['force'])

    @staticmethod
    def parse_daily_date(start_time, end_time):
        try:
            start_date = datetime.strptime(start_time, '%Y-%m-%d').replace(
                tzinfo=get_local_timezone()
            )
            end_date = datetime.strptime(end_time, '%Y-%m-%d').replace(
                tzinfo=get_local_timezone()
            )
        except Exception:
            raise SystemExit(
                'Date format error!'
            )
        dates = list()
        for delta_day in range((end_date - start_date).days + 1):
            bill_date = start_date + timedelta(days=delta_day)
            dates.append((bill_date, bill_date + timedelta(days=1)))
        return dates

    @staticmethod
    def parse_month_date(start_time, end_time):
        try:
            start_month = datetime.strptime(start_time, '%Y-%m').replace(
                tzinfo=get_local_timezone()
            )
            end_month = datetime.strptime(end_time, '%Y-%m').replace(
                tzinfo=get_local_timezone()
            )
        except Exception:
            raise SystemExit(
                'Month format error!'
            )
        months = list()
        month_range = rrule.rrule(
            rrule.MONTHLY, dtstart=start_month, until=end_month
        ).count()
        for month_delta in range(month_range):
            bill_month = start_month + relativedelta(months=month_delta)
            months.append((bill_month, bill_month + relativedelta(months=1)))
        return months
