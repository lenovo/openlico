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

import django.db.models.deletion
import timezone_field.fields
from django.db import migrations, models

import lico.core.workflow.validators


class Migration(migrations.Migration):

    dependencies = [
        ('workflow', '0001_lico_workflow_1_0_0'),
    ]

    operations = [
        migrations.CreateModel(
            name='ClockedSchedule',
            fields=[
                ('id', models.AutoField(
                    auto_created=True,
                    primary_key=True,
                    serialize=False,
                    verbose_name='ID'
                )),
                ('clocked_time', models.DateTimeField(
                    help_text='Run the task at clocked time',
                    verbose_name='Clock Time'
                )),
            ],
            options={
                'verbose_name': 'clocked',
                'verbose_name_plural': 'clocked',
                'ordering': ['clocked_time'],
            },
        ),
        migrations.CreateModel(
            name='CrontabSchedule',
            fields=[
                ('id', models.AutoField(
                    auto_created=True,
                    primary_key=True,
                    serialize=False,
                    verbose_name='ID'
                )),
                ('minute', models.CharField(
                    default='*',
                    help_text='Cron Minutes to Run. Use "*" for "all". '
                              '(Example: "0,30")',
                    max_length=240,
                    validators=[
                        lico.core.workflow.validators.minute_validator
                    ],
                    verbose_name='Minute(s)'
                )),
                ('hour', models.CharField(
                    default='*',
                    help_text='Cron Hours to Run. Use "*" for "all". '
                              '(Example: "8,20")',
                    max_length=96,
                    validators=[lico.core.workflow.validators.hour_validator],
                    verbose_name='Hour(s)'
                )),
                ('day_of_week', models.CharField(
                    default='*',
                    help_text='Cron Days Of The Week to Run. '
                              'Use "*" for "all". (Example: "0,5")',
                    max_length=64,
                    validators=[
                        lico.core.workflow.validators.day_of_week_validator
                    ],
                    verbose_name='Day(s) Of The Week'
                )),
                ('day_of_month', models.CharField(
                    default='*',
                    help_text='Cron Days Of The Month to Run. '
                              'Use "*" for "all". (Example: "1,15")',
                    max_length=124,
                    validators=[
                        lico.core.workflow.validators.day_of_month_validator
                    ],
                    verbose_name='Day(s) Of The Month'
                )),
                ('month_of_year', models.CharField(
                    default='*',
                    help_text='Cron Months Of The Year to Run. '
                              'Use "*" for "all". (Example: "0,6")',
                    max_length=64,
                    validators=[
                        lico.core.workflow.validators.month_of_year_validator
                    ],
                    verbose_name='Month(s) Of The Year'
                )),
                ('timezone', timezone_field.fields.TimeZoneField(
                    default='UTC',
                    help_text='Timezone to Run the Cron Schedule on. '
                              'Default is UTC.',
                    verbose_name='Cron Timezone'
                )),
            ],
            options={
                'verbose_name': 'crontab',
                'verbose_name_plural': 'crontabs',
                'ordering': ['month_of_year', 'day_of_month', 'day_of_week',
                             'hour', 'minute', 'timezone'],
            },
        ),
        migrations.CreateModel(
            name='WorkflowPeriodicTask',
            fields=[
                ('id', models.AutoField(
                    auto_created=True,
                    primary_key=True,
                    serialize=False,
                    verbose_name='ID'
                )),
                ('is_enabled', models.BooleanField(
                    default=True,
                    help_text='Set to False to disable the workflow'
                )),
                ('last_run_at', models.DateTimeField(
                    blank=True,
                    editable=False,
                    help_text='Datetime that the schedule '
                              'last triggered the task to run. '
                              'Reset to None if is_enabled is set to False.',
                    null=True,
                    verbose_name='Last Run Datetime'
                )),
                ('total_run_count', models.PositiveIntegerField(
                    default=0,
                    editable=False,
                    help_text='Running count of how many times '
                              'the schedule has triggered the task',
                    verbose_name='Total Run Count'
                )),
                ('clocked', models.ForeignKey(
                    blank=True,
                    help_text='Clocked Schedule to run the task on.',
                    null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    to='workflow.ClockedSchedule',
                    verbose_name='Clocked Schedule'
                )),
                ('crontab', models.ForeignKey(
                    blank=True,
                    help_text='Crontab Schedule to run the task on.',
                    null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    to='workflow.CrontabSchedule',
                    verbose_name='Crontab Schedule'
                )),
                ('workflow', models.OneToOneField(
                    help_text='The workflow that should be run',
                    on_delete=django.db.models.deletion.CASCADE,
                    to='workflow.Workflow'
                )),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, lico.core.contrib.models.ToDictMixin),
        ),
    ]
