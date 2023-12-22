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

from django.db import migrations, models

import lico.core.contrib.fields
import lico.core.contrib.models


class Migration(migrations.Migration):

    dependencies = [
        ('monitor_host', '0001_lico_monitor_host_1_0_0'),
    ]

    operations = [
        migrations.CreateModel(
            name='NodeSchedulableRes',
            fields=[
                ('id', models.AutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID')),
                ('hostname', models.CharField(
                    max_length=254, unique=True)),
                ('state', models.CharField(max_length=254, null=True)),
                ('cpu_total', models.IntegerField(null=True)),
                ('cpu_util', models.FloatField(
                    help_text='Unit: %', null=True)),
                ('mem_total', models.BigIntegerField(
                    help_text='Unit: KB', null=True)),
                ('mem_used', models.FloatField(
                    help_text='Unit: KB', null=True)),
                ('gres', models.TextField(default='{}')),
                ('create_time', lico.core.contrib.fields.DateTimeField(
                    auto_now_add=True)),
                ('update_time', lico.core.contrib.fields.DateTimeField(
                    auto_now=True)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, lico.core.contrib.models.ToDictMixin),
        ),
        migrations.RenameField(
            model_name='monitornode',
            old_name='cpu_total',
            new_name='cpu_core_per_socket',
        ),
        migrations.AddField(
            model_name='monitornode',
            name='cpu_thread_per_core',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='monitornode',
            name='hypervisor_vendor',
            field=models.CharField(default=None, max_length=100, null=True),
        ),
    ]
