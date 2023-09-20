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
from django.db import migrations, models

import lico.core.contrib.fields
import lico.core.contrib.models


class Migration(migrations.Migration):

    dependencies = [
        ('monitor_host', '0002_lico_monitor_host_1_1_0'),
    ]

    operations = [
        migrations.AddField(
            model_name='gpu',
            name='mig_mode',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='gpu',
            name='bandwidth_util',
            field=models.IntegerField(default=0, help_text='Unit: %'),
        ),
        migrations.AddField(
            model_name='gpu',
            name='driver_version',
            field=models.CharField(default='', max_length=32),
        ),
        migrations.AddField(
            model_name='gpu',
            name='pcie_generation',
            field=models.CharField(default='{}', max_length=100),
        ),
        migrations.CreateModel(
            name='MigDeviceInfo',
            fields=[
                ('id', models.AutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID')),
                ('name', models.CharField(default='', max_length=100)),
                ('gi_id', models.IntegerField(default=-1)),
                ('ci_id', models.IntegerField(default=-1)),
                ('mig_dev', models.IntegerField(default=-1)),
                ('memory_total', models.IntegerField(
                    default=0, help_text='Unit: KiB')),
                ('memory_used', models.IntegerField(
                    default=0, help_text='Unit: KiB')),
                ('sm', models.IntegerField(default=-1)),
                ('create_time', lico.core.contrib.fields.DateTimeField(
                    auto_now_add=True)),
                ('update_time', lico.core.contrib.fields.DateTimeField(
                    auto_now=True)),
                ('gpu', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='mig_device_info', to='monitor_host.Gpu')),
            ],
            options={
                'unique_together': {('gi_id', 'ci_id', 'gpu')},
            },
            bases=(models.Model, lico.core.contrib.models.ToDictMixin),
        ),
    ]

