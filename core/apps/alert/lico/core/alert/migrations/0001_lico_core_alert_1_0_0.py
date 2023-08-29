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
            name='NotifyTarget',
            fields=[
                ('id', models.AutoField(
                    auto_created=True,
                    primary_key=True,
                    serialize=False,
                    verbose_name='ID')
                 ),
                ('name', models.CharField(max_length=255, unique=True)),
                ('phone', jsonfield.fields.JSONField(),),
                ('email', jsonfield.fields.JSONField(),),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, lico.core.contrib.models.ToDictMixin),
        ),
        migrations.CreateModel(
            name='Policy',
            fields=[
                ('id', models.AutoField(
                    auto_created=True,
                    primary_key=True,
                    serialize=False,
                    verbose_name='ID')
                 ),
                ('metric_policy', models.CharField(
                    choices=[('CPUSAGE', 'cpusage'),
                             ('TEMP', 'tempature'),
                             ('NETWORK', 'network'),
                             ('DISK', 'disk'),
                             ('ELECTRIC', 'electric'),
                             ('NODE_ACTIVE', 'node_active'),
                             ('HARDWARE', 'hardware'),
                             ('GPU_UTIL', 'gpu_util'),
                             ('GPU_TEMP', 'gpu_temp'),
                             ('GPU_MEM', 'gpu_mem')],
                    max_length=20,
                    null=True)
                 ),
                ('name', models.CharField(max_length=50, unique=True)),
                ('portal', lico.core.contrib.fields.JSONCharField(
                    max_length=100)
                 ),
                ('duration', models.DurationField()),
                ('status', models.CharField(
                    choices=[('ON', 'on'), ('OFF', 'off')],
                    default='OFF',
                    max_length=10)
                 ),
                ('level', models.CharField(
                    choices=[('0', 'not set'), ('20', 'info'),
                             ('30', 'warn'), ('40', 'error'),
                             ('50', 'fatal')],
                    default=0, max_length=2)
                 ),
                ('nodes', models.TextField(default='all')),
                ('creator', models.CharField(max_length=20)),
                ('create_time', lico.core.contrib.fields.DateTimeField(
                    auto_now_add=True)
                 ),
                ('modify_time', lico.core.contrib.fields.DateTimeField(
                    auto_now=True)
                 ),
                ('wechat', models.BooleanField()),
                ('sms', models.BooleanField(default=False)),
                ('language', models.CharField(
                    choices=[
                        ('en', 'English'),
                        ('sc', 'Simplified Chinese')
                    ],
                    default='en',
                    max_length=10
                )
                ),
                ('script', models.TextField(null=True)),
                ('targets', models.ManyToManyField(
                    blank=True,
                    to='alert.NotifyTarget')
                 ),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, lico.core.contrib.models.ToDictMixin),
        ),
        migrations.CreateModel(
            name='Alert',
            fields=[
                ('id', models.AutoField(
                    auto_created=True,
                    primary_key=True,
                    serialize=False,
                    verbose_name='ID')
                 ),
                ('node', models.CharField(max_length=255)),
                ('index', models.IntegerField(null=True)),
                ('status', models.CharField(
                    choices=[
                        ('present', 'present'),
                        ('confirmed', 'confirmed'),
                        ('resolved', 'resolved')
                    ],
                    default='present',
                    max_length=20)
                 ),
                ('create_time', lico.core.contrib.fields.DateTimeField(
                    auto_now_add=True,
                    db_index=True)
                 ),
                ('comment', models.TextField()),
                ('policy', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='alert.Policy')
                 ),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, lico.core.contrib.models.ToDictMixin),
        ),
    ]
