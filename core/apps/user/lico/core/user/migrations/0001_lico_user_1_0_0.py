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

from lico.core.contrib.fields import DateTimeField
from lico.core.contrib.models import ToDictMixin


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='User',
            fields=[
                (
                    'id', models.AutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name='ID'
                    )
                ),
                (
                    'username', models.CharField(
                        max_length=32, unique=True, db_index=True
                    )
                ),
                ('first_name', models.CharField(max_length=30, null=True)),
                ('last_name', models.CharField(max_length=30, null=True)),
                ('email', models.EmailField(max_length=254, null=True)),
                (
                    'role', models.IntegerField(
                        choices=[
                            (300, 'admin'), (200, 'operator'), (100, 'user')],
                        default=100
                    )
                ),
                ('date_joined', DateTimeField(auto_now_add=True)),
                ('last_login', DateTimeField(null=True)),
                ('fail_chances', models.IntegerField(default=0)),
                (
                    'effective_time', DateTimeField(
                        auto_now_add=True
                    )
                ),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, ToDictMixin),
        ),
        migrations.CreateModel(
            name='ApiKey',
            fields=[
                (
                    'id', models.AutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name='ID'
                    )
                ),
                ('api_key', models.CharField(
                    max_length=50, null=True, unique=True)),
                ('create_time', DateTimeField(auto_now_add=True)),
                (
                    'expire_time', DateTimeField(null=True)),
                (
                    'user', models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='apikey',
                        to='user.User'),
                ),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, ToDictMixin),
        ),
        migrations.CreateModel(
            name='ImportRecordTask',
            fields=[
                ('id', models.AutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID'
                )),
                ('is_running', models.BooleanField(default=True)),
                ('owner', models.CharField(max_length=32, unique=True)),
                ('create_time', DateTimeField(auto_now_add=True)),
                ('update_time', DateTimeField(auto_now=True)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, ToDictMixin),
        ),
        migrations.CreateModel(
            name='ImportRecord',
            fields=[
                ('id', models.AutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID'
                )),
                ('row', models.IntegerField()),
                ('username', models.CharField(max_length=32)),
                ('role', models.IntegerField(
                    choices=[(300, 'admin'), (200, 'operator'), (100, 'user')],
                    default=100
                )),
                ('first_name', models.CharField(max_length=30, null=True)),
                ('last_name', models.CharField(max_length=30, null=True)),
                ('email', models.EmailField(max_length=254, null=True)),
                ('ret', models.BooleanField(null=True)),
                ('error_message', models.CharField(max_length=50, null=True)),
                ('task', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='records', to='user.ImportRecordTask'
                )),
            ],
            options={
                'unique_together': {('task', 'row', 'username')},
            },
            bases=(models.Model, ToDictMixin),
        ),
    ]
