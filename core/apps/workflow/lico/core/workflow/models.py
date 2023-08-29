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

from datetime import datetime

import croniter
import timezone_field
from django.conf import settings
from django.core.exceptions import MultipleObjectsReturned, ValidationError
from django.db import models
from django.db.models import (
    CASCADE, CharField, ForeignKey, IntegerField, TextField,
)

from lico.core.contrib.fields import DateTimeField, JSONField
from lico.core.contrib.models import Model

from . import schedules, validators


class Workflow(Model):
    CREATED = "created"
    STARTING = "starting"
    CANCELLING = "cancelling"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    IGNORE_FAILED = "ignore_failed"
    ALL_COMPLETED = "all_completed"
    RUN_POLICY_CHOICES = (
        (IGNORE_FAILED, "ignore_failed"),
        (ALL_COMPLETED, "all_completed")

    )
    STATUS_CHOICES = (
        (CREATED, "created"),
        (STARTING, "starting"),
        (CANCELLING, "cancelling"),
        (COMPLETED, "completed"),
        (FAILED, "failed"),
        (CANCELLED, "cancelled"),
    )

    name = CharField(max_length=128)
    owner = CharField(max_length=32)
    run_policy = CharField(max_length=32, choices=RUN_POLICY_CHOICES,
                           default=ALL_COMPLETED)
    max_submit_jobs = IntegerField(default=3)
    status = CharField(max_length=32, null=True, blank=True,
                       choices=STATUS_CHOICES)
    create_time = DateTimeField(auto_now_add=True)
    update_time = DateTimeField(auto_now=True)
    start_time = DateTimeField(null=True)
    description = TextField(null=True)

    def get_periodic_task(self):
        try:
            task = self.workflowperiodictask
        except WorkflowPeriodicTask.DoesNotExist:
            return None

        if task.is_enabled is False:
            return None

        data = task.as_dict(inspect_related=False)
        if task.crontab:
            data["crontab"] = {
                'day_of_month': task.crontab.day_of_month,
                'day_of_week': task.crontab.day_of_week,
                'hour': task.crontab.hour,
                'minute': task.crontab.minute,
                'month_of_year': task.crontab.month_of_year,
                'timezone': task.crontab.timezone.zone,
            }
        elif task.clocked:
            data["clocked"] = str(task.clocked.clocked_time)

        return data


class WorkflowStep(Model):
    name = CharField(max_length=128)
    order = IntegerField()
    workflow = ForeignKey(Workflow, blank=False, on_delete=CASCADE,
                          related_name='workflow_steps')
    create_time = DateTimeField(auto_now_add=True)
    update_time = DateTimeField(auto_now=True)
    description = TextField(null=True)


class WorkflowStepJob(Model):
    workflow_step = ForeignKey(WorkflowStep, blank=False, on_delete=CASCADE,
                               related_name='step_job')
    job_name = CharField(max_length=128)
    job_id = IntegerField(null=True)
    template_id = CharField(max_length=128)
    create_time = DateTimeField(auto_now_add=True)
    update_time = DateTimeField(auto_now=True)
    json_body = JSONField()


class WorkflowPeriodicTask(Model):
    workflow = models.OneToOneField(
        Workflow, CASCADE, help_text="The workflow that should be run"
    )

    is_enabled = models.BooleanField(
        default=True, help_text="Set to False to disable the workflow"
    )

    last_run_at = models.DateTimeField(
        auto_now=False, auto_now_add=False,
        editable=False, blank=True, null=True,
        verbose_name='Last Run Datetime',
        help_text='Datetime that the schedule last triggered the task to run. '
                  'Reset to None if is_enabled is set to False.'
    )
    total_run_count = models.PositiveIntegerField(
        default=0, editable=False,
        verbose_name='Total Run Count',
        help_text='Running count of how many times '
                  'the schedule has triggered the task',
    )

    # set only one schedule type, leave the other null
    crontab = models.ForeignKey(
        "CrontabSchedule", on_delete=models.CASCADE, null=True, blank=True,
        verbose_name="Crontab Schedule",
        help_text="Crontab Schedule to run the task on."
    )
    clocked = models.ForeignKey(
        "ClockedSchedule", on_delete=models.CASCADE, null=True, blank=True,
        verbose_name="Clocked Schedule",
        help_text="Clocked Schedule to run the task on."
    )

    def save(self, *a, **kw):
        if self.crontab and self.clocked:
            raise ValidationError("Crontab and clocked are mutually exclusive."
                                  " Please set just one schedule type")

        if self.crontab is None and self.clocked is None:
            raise ValidationError("Please set one schedule type")

        super().save(*a, **kw)

    @property
    def schedule(self):
        if self.crontab:
            return self.crontab.schedule
        if self.clocked:
            return self.clocked.schedule

    @property
    def is_one_off(self):
        return self.clocked is not None

    @property
    def next_run_at(self):
        # Both the task has no crontab or clocked and the task is disabled,
        # then the next_run_at is None
        if self.is_enabled is False:
            return None
        if self.clocked:
            return self.clocked.clocked_time
        if self.crontab:
            now = start_time = datetime.utcnow().astimezone(
                tz=self.crontab.timezone
            )
            if self.last_run_at:
                start_time = self.last_run_at.astimezone(
                    tz=self.crontab.timezone
                )
            itr = croniter.croniter(self.crontab.to_cron, start_time)
            next_run = itr.get_next(datetime)
            if next_run >= now:
                return next_run
            else:
                return croniter.croniter(
                    self.crontab.to_cron, now
                ).get_next(datetime)

    def as_dict_on_finished(
            self, result, is_exlucded, **kwargs
    ):
        if not is_exlucded('next_run_at'):
            result['next_run_at'] = self.next_run_at
        return result


def cronexp(field):
    """Representation of cron expression."""
    return field and str(field).replace(' ', '') or '*'


class CrontabSchedule(models.Model):
    """Timezone Aware Crontab-like schedule.

    Example:  Run every hour at 0 minutes for days of month 10-15
    minute="0", hour="*", day_of_week="*",
    day_of_month="10-15", month_of_year="*"
    """

    #
    # The worst case scenario for day of month is a list of all 31 day numbers
    # '[1, 2, ..., 31]' which has a length of 115. Likewise, minute can be
    # 0..59 and hour can be 0..23. Ensure we can accomodate these by allowing
    # 4 chars for each value (what we save on 0-9 accomodates the []).
    # We leave the other fields at their historical length.
    #
    minute = models.CharField(
        max_length=60 * 4, default='*',
        verbose_name='Minute(s)',
        help_text='Cron Minutes to Run. Use "*" for "all". (Example: "0,30")',
        validators=[validators.minute_validator],
    )
    hour = models.CharField(
        max_length=24 * 4, default='*',
        verbose_name='Hour(s)',
        help_text='Cron Hours to Run. Use "*" for "all". (Example: "8,20")',
        validators=[validators.hour_validator],
    )
    day_of_week = models.CharField(
        max_length=64, default='*',
        verbose_name='Day(s) Of The Week',
        help_text='Cron Days Of The Week to Run. Use "*" for "all". '
                  '(Example: "0,5")',
        validators=[validators.day_of_week_validator],
    )
    day_of_month = models.CharField(
        max_length=31 * 4, default='*',
        verbose_name='Day(s) Of The Month',
        help_text='Cron Days Of The Month to Run. Use "*" for "all". '
                  '(Example: "1,15")',
        validators=[validators.day_of_month_validator],
    )
    month_of_year = models.CharField(
        max_length=64, default='*',
        verbose_name='Month(s) Of The Year',
        help_text='Cron Months Of The Year to Run. Use "*" for "all". '
                  '(Example: "0,6")',
        validators=[validators.month_of_year_validator],
    )

    timezone = timezone_field.TimeZoneField(
        default="UTC",
        verbose_name='Cron Timezone',
        help_text='Timezone to Run the Cron Schedule on. Default is UTC.',
    )

    @property
    def to_cron(self):
        return '{0} {1} {2} {3} {4}'.format(
            cronexp(self.minute), cronexp(self.hour),
            cronexp(self.day_of_month), cronexp(self.month_of_year),
            cronexp(self.day_of_week))

    class Meta:
        verbose_name = 'crontab'
        verbose_name_plural = 'crontabs'
        ordering = ['month_of_year', 'day_of_month',
                    'day_of_week', 'hour', 'minute', 'timezone']

    def __str__(self):
        return '{0} {1} {2} {3} {4} (m/h/dM/MY/d) {5}'.format(
            cronexp(self.minute), cronexp(self.hour),
            cronexp(self.day_of_month), cronexp(self.month_of_year),
            cronexp(self.day_of_week), str(self.timezone)
        )

    @property
    def schedule(self):
        crontab = schedules.crontab(
            minute=self.minute,
            hour=self.hour,
            day_of_week=self.day_of_week,
            day_of_month=self.day_of_month,
            month_of_year=self.month_of_year,
        )
        if settings.USE_TZ:
            crontab = schedules.TzAwareCrontab(
                minute=self.minute,
                hour=self.hour,
                day_of_week=self.day_of_week,
                day_of_month=self.day_of_month,
                month_of_year=self.month_of_year,
                tz=self.timezone
            )
        return crontab

    @classmethod
    def from_schedule(cls, schedule):
        spec = {'minute': schedule._orig_minute,
                'hour': schedule._orig_hour,
                'day_of_week': schedule._orig_day_of_week,
                'day_of_month': schedule._orig_day_of_month,
                'month_of_year': schedule._orig_month_of_year,
                'timezone': schedule.tz
                }
        try:
            return cls.objects.get(**spec)
        except cls.DoesNotExist:
            return cls(**spec)
        except MultipleObjectsReturned:
            cls.objects.filter(**spec).delete()
            return cls(**spec)


class ClockedSchedule(models.Model):
    """clocked schedule."""

    clocked_time = models.DateTimeField(
        verbose_name="Clock Time",
        help_text='Run the task at clocked time',
    )

    class Meta:
        verbose_name = 'clocked'
        verbose_name_plural = 'clocked'
        ordering = ['clocked_time']

    def __str__(self):
        return '{}'.format(self.clocked_time)

    @property
    def schedule(self):
        c = schedules.clocked(clocked_time=self.clocked_time)
        return c

    @classmethod
    def from_schedule(cls, schedule):
        spec = {'clocked_time': schedule.clocked_time}
        try:
            return cls.objects.get(**spec)
        except cls.DoesNotExist:
            return cls(**spec)
        except MultipleObjectsReturned:
            cls.objects.filter(**spec).delete()
            return cls(**spec)
