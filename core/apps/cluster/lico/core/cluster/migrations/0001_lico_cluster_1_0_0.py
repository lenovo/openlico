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

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models

from lico.core.contrib.models import ToDictMixin


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Chassis',
            fields=[
                ('id', models.AutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID'
                )),
                ('name', models.CharField(max_length=255, unique=True)),
                ('location_u', models.IntegerField(default=1)),
                ('machine_type', models.TextField()),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, ToDictMixin),
        ),
        migrations.CreateModel(
            name='Node',
            fields=[
                ('id', models.AutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID'
                )),
                ('hostname', models.CharField(max_length=255, unique=True)),
                ('type', models.TextField()),
                ('machinetype', models.TextField()),
                ('mgt_address', models.TextField(
                    validators=[django.core.validators.validate_ipv46_address]
                )),
                ('bmc_address', models.TextField(
                    null=True,
                    validators=[django.core.validators.validate_ipv46_address]
                )),
                ('location_u', models.IntegerField(default=1)),
                ('chassis', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    to='cluster.Chassis'
                )),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, ToDictMixin),
        ),
        migrations.CreateModel(
            name='Room',
            fields=[
                ('id', models.AutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID'
                )),
                ('name', models.CharField(max_length=255, unique=True)),
                ('location', models.TextField()),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, ToDictMixin),
        ),
        migrations.CreateModel(
            name='Row',
            fields=[
                ('id', models.AutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID'
                )),
                ('name', models.CharField(max_length=255, unique=True)),
                ('index', models.IntegerField()),
                ('room', models.ForeignKey(
                    null=True, on_delete=django.db.models.deletion.PROTECT,
                    related_name='rows', to='cluster.Room'
                )),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, ToDictMixin),
        ),
        migrations.CreateModel(
            name='Rack',
            fields=[
                ('id', models.AutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID'
                )),
                ('name', models.CharField(max_length=255, unique=True)),
                ('col', models.IntegerField()),
                ('row', models.ForeignKey(
                    null=True, on_delete=django.db.models.deletion.PROTECT,
                    related_name='racks', to='cluster.Row'
                )),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, ToDictMixin),
        ),
        migrations.CreateModel(
            name='NodeGroup',
            fields=[
                ('id', models.AutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID'
                )),
                ('name', models.CharField(max_length=255, unique=True)),
                ('nodes', models.ManyToManyField(
                    related_name='groups', to='cluster.Node'
                )),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, ToDictMixin),
        ),
        migrations.AddField(
            model_name='node',
            name='rack',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='nodes',
                to='cluster.Rack'
            ),
        ),
        migrations.AddField(
            model_name='chassis',
            name='rack',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='chassis',
                to='cluster.Rack'
            ),
        ),
    ]
