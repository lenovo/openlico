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


class Migration(migrations.Migration):
    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='OperationLog',
            fields=[
                (
                    'id',
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID')
                ),
                (
                    'module',
                    models.CharField(
                        choices=[
                            ('user', 'user'),
                            ('job', 'job'),
                            ('node', 'node'),
                            ('alert', 'alert'),
                            ('policy', 'policy'),
                            ('billgroup', 'billgroup'),
                            ('deposit', 'deposit'),
                            ('osgroup', 'osgroup')],
                        max_length=128)
                ),
                (
                    'operate_time',
                    models.DateTimeField(
                        auto_now_add=True)
                ),
                (
                    'operation',
                    models.CharField(
                        choices=[
                            ('create', 'create'),
                            ('update', 'update'),
                            ('delete', 'delete'),
                            ('recharge', 'recharge'),
                            ('chargeback', 'chargeback'),
                            ('solve', 'solve'),
                            ('confirm', 'confirm'),
                            ('turn_on', 'turn_on'),
                            ('turn_off', 'turn_off'),
                            ('cancel', 'cancel'),
                            ('rerun', 'rerun'),
                            ('comment', 'comment')],
                        max_length=128)
                ),
                (
                    'operator',
                    models.CharField(
                        max_length=256)
                ),
            ],
        ),
        migrations.CreateModel(
            name='LogDetail',
            fields=[
                (
                    'id',
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID')
                ),
                (
                    'object_id',
                    models.IntegerField()
                ),
                (
                    'name',
                    models.CharField(max_length=256)
                ),
                (
                    'optlog',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='target', to='base.OperationLog')
                ),
            ],
        ),
    ]
