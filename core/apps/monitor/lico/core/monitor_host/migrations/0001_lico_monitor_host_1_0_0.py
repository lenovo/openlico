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

from . import CreatePreferenceData


class Migration(migrations.Migration):
    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='MonitorNode',
            fields=[
                (
                    'hostname', models.CharField(
                        max_length=254,
                        primary_key=True,
                        serialize=False,
                        unique=True
                    )
                ),
                (
                    'cpu_util', models.FloatField(default=0)),
                (
                    'power_status', models.BooleanField(
                        default=False,
                        help_text='True: power on; False: power off'
                    )
                ),
                (
                    'disk_total',
                    models.FloatField(
                        default=0, help_text=b'unit:GB')
                ),
                (
                    'disk_used',
                    models.FloatField(
                        default=0, help_text=b'unit:GB'
                    )
                ),
                (
                    'memory_total',
                    models.FloatField(
                        default=0, help_text=b'unit:KB'
                    )
                ),
                (
                    'memory_used',
                    models.FloatField(
                        default=0, help_text=b'unit:KB'
                    )
                ),
                (
                    'eth_in',
                    models.FloatField(
                        default=0, help_text=b'unit:MB/s'
                    )
                ),
                (
                    'eth_out',
                    models.FloatField(
                        default=0, help_text=b'unit:MB/s'
                    )
                ),
                (
                    'ib_in',
                    models.FloatField(
                        default=0, help_text=b'unit:MB/s'
                    )
                ),
                (
                    'ib_out',
                    models.FloatField(
                        default=0, help_text=b'unit:MB/s'
                    )
                ),
                (
                    'cpu_total', models.IntegerField(
                        default=0
                    )
                ),
                (
                    'cpu_socket_num', models.IntegerField(
                        default=0
                    )
                ),
                (
                    'health',
                    models.CharField(
                        default='unknown', max_length=100
                    )
                ),
                (
                    'create_time',
                    lico.core.contrib.fields.DateTimeField(
                        auto_now_add=True
                    )
                ),
                (
                    'update_time',
                    lico.core.contrib.fields.DateTimeField(
                        auto_now=True
                    )
                ),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, lico.core.contrib.models.ToDictMixin),
        ),
        migrations.CreateModel(
            name='Preference',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True,
                                        serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=256)),
                ('value', models.TextField()),
                ('username', models.CharField(
                    help_text=b'null:scope is global, '
                    b'otherwise scope is local',
                    max_length=32, null=True)),
                ('create_time',
                 lico.core.contrib.fields.DateTimeField(auto_now_add=True)),
                ('modify_time',
                 lico.core.contrib.fields.DateTimeField(auto_now=True)),
            ],
            options={
                'unique_together': {('name', 'username')},
            },
            bases=(models.Model, lico.core.contrib.models.ToDictMixin),
        ),
        CreatePreferenceData(
            name='monitor_host.policy.node.status',
            value='cpu_core',
        ),
        migrations.CreateModel(
            name='HardwareHealth',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True,
                                        serialize=False, verbose_name='ID')),
                ('health', models.CharField(max_length=100)),
                ('name', models.CharField(max_length=100)),
                ('states', models.CharField(max_length=100)),
                ('units', models.CharField(max_length=100, null=True)),
                ('value',
                 models.CharField(default='', max_length=100, null=True)),
                ('type', models.CharField(max_length=100)),
                ('create_time',
                 lico.core.contrib.fields.DateTimeField(auto_now_add=True)),
                ('monitor_node',
                 models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                   related_name='hardware_health',
                                   to='monitor_host.MonitorNode')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, lico.core.contrib.models.ToDictMixin),
        ),
        migrations.CreateModel(
            name='Gpu',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True,
                                        serialize=False, verbose_name='ID')),
                ('index', models.IntegerField()),
                ('occupation', models.BooleanField(
                    default=False,
                    help_text='True: used; False: free')
                 ),
                ('type', models.CharField(default='', max_length=100)),
                ('memory_used',
                 models.IntegerField(default=0, help_text='Unit: KiB')),
                ('memory_total',
                 models.IntegerField(default=0, help_text='Unit: KiB')),
                ('util', models.IntegerField(default=0, help_text='Unit: %')),
                ('memory_util',
                 models.IntegerField(default=0, help_text='Unit: %')),
                ('temperature',
                 models.IntegerField(default=0, help_text='Unit: C')),
                ('monitor_node',
                 models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                   related_name='gpu',
                                   to='monitor_host.MonitorNode')),
            ],
            options={
                'unique_together': {('index', 'monitor_node')},
            },
            bases=(models.Model, lico.core.contrib.models.ToDictMixin),
        ),
    ]
