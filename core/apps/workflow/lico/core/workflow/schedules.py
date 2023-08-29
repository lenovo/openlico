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

from collections import namedtuple
from datetime import datetime

from celery import schedules as _schedules
from celery.utils.time import maybe_make_aware
from pytz import utc

crontab = _schedules.crontab

schedstate = namedtuple('schedstate', ('is_due', 'next'))


class TzAwareCrontab(crontab):
    """Timezone Aware Crontab."""

    def __init__(self, minute='*', hour='*', day_of_week='*',
                 day_of_month='*', month_of_year='*', tz=utc):
        """Overwrite Crontab constructor to include a timezone argument."""
        self._tz = tz

        nowfun = self.nowfunc

        super().__init__(
            minute=minute, hour=hour, day_of_week=day_of_week,
            day_of_month=day_of_month,
            month_of_year=month_of_year, nowfun=nowfun
        )

    @property
    def tz(self):
        return self._tz

    def nowfunc(self):
        return self.tz.normalize(
            utc.localize(datetime.utcnow())
        )

    def is_due(self, last_run_at):
        """Calculate when the next run will take place.

        Return tuple of (is_due, next_time_to_check).
        The last_run_at argument needs to be timezone aware.

        """
        # convert last_run_at to the schedule timezone
        last_run_at = last_run_at.astimezone(self.tz)

        rem_delta = self.remaining_estimate(last_run_at)
        rem = max(rem_delta.total_seconds(), 0)
        due = rem == 0
        if due:
            rem_delta = self.remaining_estimate(self.now())
            rem = max(rem_delta.total_seconds(), 0)
        return schedstate(due, rem)

    # Needed to support pickling
    def __repr__(self):
        return """<crontab: {0._orig_minute} {0._orig_hour}
         {0._orig_day_of_week} {0._orig_day_of_month}
          {0._orig_month_of_year} (m/h/d/dM/MY), {0.tz}>
        """.format(self)

    def __reduce__(self):
        return (self.__class__, (self._orig_minute,
                                 self._orig_hour,
                                 self._orig_day_of_week,
                                 self._orig_day_of_month,
                                 self._orig_month_of_year,
                                 self.tz), None)

    def __eq__(self, other):
        if isinstance(other, crontab):
            return (other.month_of_year == self.month_of_year
                    and other.day_of_month == self.day_of_month
                    and other.day_of_week == self.day_of_week
                    and other.hour == self.hour
                    and other.minute == self.minute
                    and other.tz == self.tz)
        return NotImplemented


NEVER_CHECK_TIMEOUT = 100000000


class clocked(_schedules.BaseSchedule):
    """clocked schedule.

    Depends on PeriodicTask one_off=True
    """

    def __init__(self, clocked_time, nowfun=None, app=None):
        """Initialize clocked."""
        self.clocked_time = maybe_make_aware(clocked_time)
        super(clocked, self).__init__(nowfun=nowfun, app=app)

    def remaining_estimate(self, last_run_at):
        return self.clocked_time - self.now()

    def is_due(self, last_run_at):
        rem_delta = self.remaining_estimate(None)
        remaining_s = max(rem_delta.total_seconds(), 0)
        if remaining_s == 0:
            return _schedules.schedstate(is_due=True, next=NEVER_CHECK_TIMEOUT)
        return _schedules.schedstate(is_due=False, next=remaining_s)

    def __repr__(self):
        return '<clocked: {}>'.format(self.clocked_time)

    def __eq__(self, other):
        if isinstance(other, clocked):
            return self.clocked_time == other.clocked_time
        return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __reduce__(self):
        return self.__class__, (self.clocked_time, self.nowfun)
