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
import jsonfield.fields
from django.db import migrations, models

import lico.core.contrib.fields
import lico.core.contrib.models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='BillGroup',
            fields=[
                ('id', models.AutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID')
                 ),
                ('name', models.CharField(
                    default='default_bill_group', max_length=20, unique=True)
                 ),
                ('balance', models.FloatField(default=0)),
                ('charged', models.FloatField(default=0)),
                ('used_time', models.BigIntegerField(default=0)),
                ('used_credits', models.FloatField(default=0)),
                ('description', models.CharField(
                    blank=True, default='', max_length=200)
                 ),
                ('charge_rate', models.FloatField(
                    default=1, help_text='unit:ccy per core*hour')
                 ),
                ('cr_minute', models.FloatField(
                    blank=True, help_text='unit:ccy per core*minute',
                    null=True)
                 ),
                ('cr_display_type', models.CharField(
                    choices=[('hour', 'hour'), ('minute', 'minute')],
                    default='hour', max_length=32)
                 ),
                ('last_operation_time',
                 lico.core.contrib.fields.DateTimeField(auto_now=True)
                 ),
                ('gres_charge_rate', jsonfield.fields.JSONField(default={})),
                ('gcr_minute', jsonfield.fields.JSONField(
                    blank=True, default={}, null=True)
                 ),
                ('gcr_display_type', jsonfield.fields.JSONField(default={})),
                ('memory_charge_rate', models.FloatField(
                    default=1, help_text='unit:ccy per MB*hour')
                 ),
                ('mcr_minute', models.FloatField(
                    blank=True, help_text='unit:ccy per MB*minute', null=True)
                 ),
                ('mcr_display_type', models.CharField(
                    choices=[('hour', 'hour'), ('minute', 'minute')],
                    default='hour', max_length=32)
                 ),
                ('storage_charge_rate', models.FloatField(
                    default=1, help_text='unit:ccy per GB*day')
                 ),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, lico.core.contrib.models.ToDictMixin),
        ),
        migrations.CreateModel(
            name='Gresource',
            fields=[
                ('id', models.AutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID')
                 ),
                ('code', models.CharField(max_length=30, unique=True)),
                ('display_name', models.CharField(max_length=126)),
                ('unit', models.CharField(max_length=126)),
                ('create_time', lico.core.contrib.fields.DateTimeField(
                    auto_now_add=True)
                 ),
                ('update_time', lico.core.contrib.fields.DateTimeField(
                    auto_now=True)
                 ),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, lico.core.contrib.models.ToDictMixin),
        ),
        migrations.CreateModel(
            name='JobBillingStatement',
            fields=[
                ('id', models.AutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID')
                 ),
                ('job_id', models.CharField(
                    blank=True, default='', max_length=32, unique=True)
                 ),
                ('job_name', models.CharField(
                    blank=True, default='', max_length=128)
                 ),
                ('scheduler_id', models.CharField(
                    blank=True, db_index=True, default='', max_length=32)
                 ),
                ('submitter', models.CharField(
                    blank=True, db_index=True, default='', max_length=32)
                 ),
                ('bill_group_id', models.IntegerField()),
                ('bill_group_name', models.CharField(
                    db_index=True, max_length=32)
                 ),
                ('queue', models.CharField(
                    blank=True, default='', max_length=128)
                 ),
                ('job_create_time', lico.core.contrib.fields.DateTimeField(
                    null=True)
                 ),
                ('job_start_time', lico.core.contrib.fields.DateTimeField(
                    null=True)
                 ),
                ('job_end_time', lico.core.contrib.fields.DateTimeField(
                    null=True)
                 ),
                ('job_runtime', models.IntegerField(
                    blank=True, default=0, help_text='unit: second')
                 ),
                ('charge_rate', models.FloatField(
                    default=1, help_text='unit:ccy per core*hour')
                 ),
                ('cpu_count', models.FloatField(blank=True, default=0)),
                ('cpu_cost', models.FloatField(blank=True, default=0)),
                ('gres_charge_rate', jsonfield.fields.JSONField(default={})),
                ('gres_count', jsonfield.fields.JSONField(
                    blank=True, default={})
                 ),
                ('gres_cost', jsonfield.fields.JSONField(
                    blank=True, default={})
                 ),
                ('memory_charge_rate', models.FloatField(
                    default=1, help_text='unit:ccy per MB*hour')
                 ),
                ('memory_count', models.FloatField(
                    blank=True, default=0, help_text='unit:MB')
                 ),
                ('memory_cost', models.FloatField(
                    blank=True, default=0, help_text='unit:ccy')
                 ),
                ('discount', models.DecimalField(
                    blank=True, decimal_places=2, default=1,
                    max_digits=3, null=True)
                 ),
                ('total_cost', models.FloatField()),
                ('billing_cost', models.FloatField()),
                ('create_time', lico.core.contrib.fields.DateTimeField(
                    auto_now_add=True, db_index=True)
                 ),
                ('update_time', lico.core.contrib.fields.DateTimeField(
                    auto_now=True)
                 ),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, lico.core.contrib.models.ToDictMixin),
        ),
        migrations.CreateModel(
            name='StorageBillingStatement',
            fields=[
                ('id', models.AutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID')
                 ),
                ('path', models.CharField(max_length=512)),
                ('billing_date', lico.core.contrib.fields.DateTimeField()),
                ('username', models.CharField(
                    db_index=True, max_length=32)
                 ),
                ('bill_group_id', models.IntegerField()),
                ('bill_group_name', models.CharField(
                    db_index=True, max_length=32)
                 ),
                ('storage_charge_rate', models.FloatField(
                    default=1, help_text='unit:ccy per GB*day')
                 ),
                ('storage_count', models.FloatField(
                    blank=True, default=0, help_text='unit:GB')
                 ),
                ('storage_capacity', models.FloatField(
                    blank=True, default=0, help_text='unit:GB')
                 ),
                ('storage_cost', models.FloatField(
                    blank=True, default=0, help_text='unit:ccy')
                 ),
                ('discount', models.DecimalField(
                    blank=True, decimal_places=2, default=1,
                    max_digits=3, null=True)
                 ),
                ('billing_cost', models.FloatField()),
                ('create_time', lico.core.contrib.fields.DateTimeField(
                    auto_now_add=True, db_index=True)
                 ),
                ('update_time',
                 lico.core.contrib.fields.DateTimeField(auto_now=True)
                 ),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, lico.core.contrib.models.ToDictMixin),
        ),
        migrations.CreateModel(
            name='UserBillGroupMapping',
            fields=[
                ('id', models.AutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID')
                 ),
                ('username', models.CharField(max_length=32, unique=True)
                 ),
                ('create_time', lico.core.contrib.fields.DateTimeField(
                    auto_now_add=True)
                 ),
                ('update_time', lico.core.contrib.fields.DateTimeField(
                    auto_now=True)
                 ),
                ('bill_group', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='mapping', to='accounting.BillGroup')
                 ),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, lico.core.contrib.models.ToDictMixin),
        ),
        migrations.CreateModel(
            name='Discount',
            fields=[
                ('id', models.AutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID')
                 ),
                ('type', models.CharField(
                    choices=[('user', 'user'), ('usergroup', 'usergroup')],
                    max_length=32)
                 ),
                ('name', models.CharField(max_length=32)),
                ('discount', models.DecimalField(
                    decimal_places=2, default=1, max_digits=3)
                 ),
                ('create_time', lico.core.contrib.fields.DateTimeField(
                    auto_now_add=True, db_index=True)
                 ),
                ('update_time', lico.core.contrib.fields.DateTimeField(
                    auto_now=True)
                 ),
            ],
            options={
                'unique_together': {('type', 'name')},
            },
            bases=(models.Model, lico.core.contrib.models.ToDictMixin),
        ),
        migrations.CreateModel(
            name='Deposit',
            fields=[
                ('id', models.AutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID')
                 ),
                ('user', models.CharField(max_length=32, null=True)),
                ('credits', models.FloatField(default=0)),
                ('apply_time', lico.core.contrib.fields.DateTimeField(
                    null=True)
                 ),
                ('approved_time', lico.core.contrib.fields.DateTimeField(
                    null=True)
                 ),
                ('billing_type', models.CharField(
                    blank=True,
                    choices=[('', ''), ('job', 'job'), ('storage', 'storage')],
                    default='', max_length=16, null=True)
                 ),
                ('billing_id', models.IntegerField(null=True)),
                ('balance', models.FloatField()),
                ('bill_group', models.ForeignKey(
                    db_column='bill_group', null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    to='accounting.BillGroup')
                 ),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, lico.core.contrib.models.ToDictMixin),
        ),
        migrations.CreateModel(
            name='BillGroupStoragePolicy',
            fields=[
                ('id', models.AutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID')
                 ),
                ('storage_charge_rate', models.FloatField(
                    default=1, help_text='unit:ccy per GB*day')
                 ),
                ('path_list', jsonfield.fields.JSONField(default=[])),
                ('create_time', lico.core.contrib.fields.DateTimeField(
                    auto_now_add=True)
                 ),
                ('last_operation_time',
                 lico.core.contrib.fields.DateTimeField(auto_now=True)
                 ),
                ('bill_group', models.ForeignKey(
                    null=True, on_delete=django.db.models.deletion.CASCADE,
                    to='accounting.BillGroup')
                 ),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, lico.core.contrib.models.ToDictMixin),
        ),
        migrations.CreateModel(
            name='BillGroupQueuePolicy',
            fields=[
                ('id', models.AutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID')
                 ),
                ('charge_rate', models.FloatField(
                    default=1, help_text='unit:ccy per core*hour')
                 ),
                ('cr_minute', models.FloatField(
                    blank=True, help_text='unit:ccy per core*minute',
                    null=True)
                 ),
                ('cr_display_type', models.CharField(
                    choices=[('hour', 'hour'), ('minute', 'minute')],
                    default='hour', max_length=32)
                 ),
                ('gres_charge_rate', jsonfield.fields.JSONField(default={})),
                ('gcr_minute', jsonfield.fields.JSONField(
                    blank=True, default={}, null=True)
                 ),
                ('gcr_display_type', jsonfield.fields.JSONField(default={})),
                ('memory_charge_rate', models.FloatField(
                    default=1, help_text='unit:ccy per MB*hour')
                 ),
                ('mcr_minute', models.FloatField(
                    blank=True, help_text='unit:ccy per MB*minute', null=True)
                 ),
                ('mcr_display_type', models.CharField(
                    choices=[('hour', 'hour'), ('minute', 'minute')],
                    default='hour', max_length=32)
                 ),
                ('queue_list', jsonfield.fields.JSONField(default=[])),
                ('create_time', lico.core.contrib.fields.DateTimeField(
                    auto_now_add=True)
                 ),
                ('last_operation_time',
                 lico.core.contrib.fields.DateTimeField(auto_now=True)
                 ),
                ('bill_group', models.ForeignKey(
                    null=True, on_delete=django.db.models.deletion.CASCADE,
                    to='accounting.BillGroup')
                 ),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, lico.core.contrib.models.ToDictMixin),
        ),
        migrations.CreateModel(
            name='StorageBillingRecord',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True,
                                        serialize=False, verbose_name='ID')),
                ('username', models.CharField(max_length=32)),
                ('billing_date', lico.core.contrib.fields.DateTimeField()),
                ('create_time',
                 lico.core.contrib.fields.DateTimeField(auto_now_add=True)),
                ('update_time',
                 lico.core.contrib.fields.DateTimeField(auto_now=True)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, lico.core.contrib.models.ToDictMixin),
        ),
        migrations.CreateModel(
            name='BillingFile',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True,
                                        serialize=False, verbose_name='ID')),
                ('filename', models.CharField(default='', max_length=128)),
                ('billing_type', models.CharField(
                    choices=[('user', 'user'), ('cluster', 'cluster')],
                    max_length=16)),
                ('period', models.CharField(
                    choices=[('daily', 'daily'), ('monthly', 'monthly')],
                    max_length=16)),
                ('username', models.CharField(db_index=True, max_length=32)),
                ('billing_date', models.DateField()),
                ('create_time',
                 lico.core.contrib.fields.DateTimeField(auto_now_add=True,
                                                        db_index=True)),
                ('update_time',
                 lico.core.contrib.fields.DateTimeField(auto_now=True)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, lico.core.contrib.models.ToDictMixin),
        ),
    ]
