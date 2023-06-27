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

import django.db.models.deletion
from django.db import migrations, models

import lico.core.contrib.models


class Migration(migrations.Migration):
    dependencies = [
        ('monitor_host', '0003_lico_monitor_host_1_4_0'),
    ]

    operations = [
        migrations.CreateModel(
            name='Cluster',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True,
                                        serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('metric', models.CharField(max_length=100)),
                ('value', models.TextField(null=True)),
                ('create_time', lico.core.contrib.fields.DateTimeField(
                    auto_now_add=True)),
                ('update_time', lico.core.contrib.fields.DateTimeField(
                    auto_now=True)),
            ],
            options={
                'unique_together': {('name', 'metric')},
            },
            bases=(models.Model, lico.core.contrib.models.ToDictMixin),
        ),
        migrations.CreateModel(
            name='GpuLogicalDevice',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True,
                                        serialize=False, verbose_name='ID')),
                ('dev_id', models.CharField(max_length=100)),
                ('metric', models.CharField(max_length=100)),
                ('value', models.TextField(default='')),
                ('units', models.CharField(max_length=100, null=True)),
                ('create_time', lico.core.contrib.fields.DateTimeField(
                    auto_now_add=True)),
                ('update_time', lico.core.contrib.fields.DateTimeField(
                    auto_now=True)),
            ],
            bases=(models.Model, lico.core.contrib.models.ToDictMixin),
        ),
        migrations.CreateModel(
            name='VNC',
            fields=[
                ('id', models.AutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID')),
                ('index', models.CharField(max_length=100)),
                ('detail', lico.core.contrib.fields.JSONField(null=True)),
                ('create_time',
                 lico.core.contrib.fields.DateTimeField(auto_now_add=True)),
                ('update_time',
                 lico.core.contrib.fields.DateTimeField(auto_now=True)),
            ],
            bases=(models.Model, lico.core.contrib.models.ToDictMixin),
        ),
        migrations.RenameField(
            model_name='monitornode',
            old_name='power_status',
            new_name='node_active',
        ),
        migrations.RemoveField(
            model_name='gpu',
            name='memory_util',
        ),
        migrations.AddField(
            model_name='gpu',
            name='vendor',
            field=models.IntegerField(
                choices=[(0, 'NVIDIA'), (1, 'INTEL'), (2, 'AMD')], null=True),
        ),
        migrations.AddField(
            model_name='monitornode',
            name='cpu_load',
            field=models.FloatField(null=True),
        ),
        migrations.AddField(
            model_name='monitornode',
            name='power',
            field=models.FloatField(null=True),
        ),
        migrations.AddField(
            model_name='monitornode',
            name='temperature',
            field=models.FloatField(help_text='Unit: C', null=True),
        ),
        migrations.AlterField(
            model_name='gpu',
            name='bandwidth_util',
            field=models.IntegerField(help_text='Unit: %', null=True),
        ),
        migrations.AlterField(
            model_name='gpu',
            name='driver_version',
            field=models.CharField(default='', max_length=100),
        ),
        migrations.AlterField(
            model_name='gpu',
            name='memory_used',
            field=models.IntegerField(help_text='Unit: KiB', null=True),
        ),
        migrations.AlterField(
            model_name='gpu',
            name='pcie_generation',
            field=lico.core.contrib.fields.JSONField(default=dict),
        ),
        migrations.AlterField(
            model_name='gpu',
            name='temperature',
            field=models.IntegerField(help_text='Unit: C', null=True),
        ),
        migrations.AlterField(
            model_name='gpu',
            name='util',
            field=models.IntegerField(help_text='Unit: %', null=True),
        ),
        migrations.AlterField(
            model_name='monitornode',
            name='cpu_util',
            field=models.FloatField(help_text='Unit: %', null=True),
        ),
        migrations.AlterField(
            model_name='monitornode',
            name='disk_total',
            field=models.FloatField(default=0, help_text=b'unit:GiB'),
        ),
        migrations.AlterField(
            model_name='monitornode',
            name='disk_used',
            field=models.FloatField(help_text=b'unit:GiB', null=True),
        ),
        migrations.AlterField(
            model_name='monitornode',
            name='eth_in',
            field=models.FloatField(help_text=b'unit:MiB/s', null=True),
        ),
        migrations.AlterField(
            model_name='monitornode',
            name='eth_out',
            field=models.FloatField(help_text=b'unit:MiB/s', null=True),
        ),
        migrations.AlterField(
            model_name='monitornode',
            name='ib_in',
            field=models.FloatField(help_text=b'unit:MiB/s', null=True),
        ),
        migrations.AlterField(
            model_name='monitornode',
            name='ib_out',
            field=models.FloatField(help_text=b'unit:MiB/s', null=True),
        ),
        migrations.AlterField(
            model_name='monitornode',
            name='memory_total',
            field=models.FloatField(default=0, help_text=b'unit:KiB'),
        ),
        migrations.AlterField(
            model_name='monitornode',
            name='memory_used',
            field=models.FloatField(help_text=b'unit:KiB', null=True),
        ),
        migrations.DeleteModel(
            name='MigDeviceInfo',
        ),
        migrations.AddField(
            model_name='vnc',
            name='monitor_node',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='vnc',
                to='monitor_host.MonitorNode'
            ),
        ),
        migrations.AddField(
            model_name='gpulogicaldevice',
            name='gpu',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='gpu_logical_device',
                to='monitor_host.Gpu'
            ),
        ),
        migrations.AlterUniqueTogether(
            name='vnc',
            unique_together={('monitor_node', 'index')},
        ),
        migrations.AlterUniqueTogether(
            name='gpulogicaldevice',
            unique_together={('gpu', 'dev_id', 'metric')},
        ),
    ]
