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
import os.path
import sys
import tempfile
from subprocess import CalledProcessError, check_output  # nosec B404

from celery.schedules import crontab
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand

from . import print_green, print_red


class Command(BaseCommand):
    help = 'sync account timer for scheduler'

    def add_arguments(self, parser):
        exclusive_group = parser.add_mutually_exclusive_group(required=True)
        exclusive_group.add_argument(
            '--enable', action='store_true',
            help='Only enable sync account to crontab'
        )
        exclusive_group.add_argument(
            '--disable', action='store_true',
            help='Only disable sync account to crontab'
        )
        parser.add_argument(
            '--time', default='',
            help="""
            Sync account interval time.
            Time Format:
                {minute} {hour} {day-of-month} {month} {day-of-week}.
            e.g.
                */10 * * * *
            """
        )

    def minute_validator(self, value):
        """Validate minutes crontab value."""
        crontab._expand_cronspec(value, 60, 0)

    def hour_validator(self, value):
        """Validate hours crontab value."""
        crontab._expand_cronspec(value, 24, 0)

    def day_of_month_validator(self, value):
        """Validate day of month crontab value."""
        crontab._expand_cronspec(value, 31, 1)

    def month_of_year_validator(self, value):
        """Validate month crontab value."""
        crontab._expand_cronspec(value, 12, 1)

    def day_of_week_validator(self, value):
        """Validate day of week crontab value."""
        crontab._expand_cronspec(value, 7, 0)

    def get_interval(self, interval_time):
        if not interval_time:
            return '*/5 * * * *'
        time_list = interval_time.split()
        if len(time_list) != 5:
            print_red('Time format error: {0}'.format(interval_time))
            sys.exit(1)
        time_validator = [
            self.minute_validator, self.hour_validator,
            self.day_of_month_validator, self.month_of_year_validator,
            self.day_of_week_validator]
        try:
            for index, time_interval in enumerate(time_list):
                time_validator[index](time_interval)
        except ValidationError as e:
            print_red(e)
            print_red('Time format error: {0}'.format(interval_time))
            sys.exit(1)
        return interval_time

    def handle(self, *args, **options):
        interval = self.get_interval(options['time'])
        sync_acc_cmd = "{0} sync_account --log-config".format(
            os.environ.get('_', 'lico'))
        command = '\n{0} '.format(interval) + sync_acc_cmd + '\n'
        out = self._exec_cmd(['crontab', '-l'])
        out_list = out.split('\n')
        if options['enable']:
            if command.strip() in out:
                print_green('sync account timer enabled')
                sys.exit(0)
            for out_value in out_list.copy():
                if out_value.endswith(sync_acc_cmd):
                    out_list.remove(out_value)
            self._update_crontab('\n'.join(out_list) + command)
            print_green('Successfully enable sync account timer')
            sys.exit(0)

        if options['disable']:
            if sync_acc_cmd not in out:
                print_green('sync account timer disabled')
                sys.exit(0)
            for out_value in out_list.copy():
                if out_value.endswith(sync_acc_cmd):
                    out_list.remove(out_value)
            crontab_str = ''.join(filter(None, out_list))
            write_cmd = "\n" + crontab_str + "\n" if crontab_str else ""
            self._update_crontab(write_cmd)
            print_green('Successfully disable sync account timer')

    def _update_crontab(self, command):
        filed, path = tempfile.mkstemp()
        fileh = os.fdopen(filed, 'wb')
        fileh.write(command.encode('utf-8'))
        fileh.close()
        self._exec_cmd(['crontab', path])
        os.unlink(path)

    def _exec_cmd(self, cmd):
        try:
            out = check_output(cmd)  # nosec B603
        except CalledProcessError:
            return ''
        return out.decode()
