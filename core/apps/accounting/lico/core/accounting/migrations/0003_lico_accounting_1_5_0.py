# Copyright 2023-present Lenovo
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
from django.db import migrations, models

import lico.core.contrib.fields
import lico.core.contrib.models


class Migration(migrations.Migration):

    dependencies = [
        ('alert', '0004_lico_core_alert_1_3_0'),
        ('accounting', '0002_lico_accounting_1_4_0'),
    ]

    operations = [
        migrations.AddField(
            model_name='billgroup',
            name='balance_alert',
            field=models.BooleanField(default=False),
        ),
        migrations.CreateModel(
            name='BalanceAlertSetting',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True,
                                        serialize=False, verbose_name='ID')),
                ('balance_threshold', models.FloatField(default=0)),
                ('targets', models.ManyToManyField(
                    blank=True, to='alert.NotifyTarget')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, lico.core.contrib.models.ToDictMixin),
        ),
        migrations.CreateModel(
            name='BalanceAlert',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True,
                                        serialize=False, verbose_name='ID')),
                ('create_time', lico.core.contrib.fields.DateTimeField(
                    auto_now_add=True)),
                ('bill_group', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='alert', to='accounting.BillGroup')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, lico.core.contrib.models.ToDictMixin),
        ),
    ]
