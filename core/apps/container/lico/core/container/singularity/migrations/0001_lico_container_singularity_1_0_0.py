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

import lico.core.contrib.fields
import lico.core.contrib.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='SingularityImage',
            fields=[
                ('id', models.AutoField(
                    auto_created=True,
                    primary_key=True,
                    serialize=False,
                    verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('image_path', models.TextField()),
                ('description', models.TextField(null=True)),
                ('framework', models.CharField(max_length=32)),
                ('create_time', lico.core.contrib.fields.DateTimeField(
                    auto_now_add=True)
                 ),
                ('version', models.CharField(max_length=32, null=True)),
                ('username', models.CharField(default='', max_length=32)),
                ('status', models.IntegerField(
                    choices=[
                        (0, 'PENDING'),
                        (1, 'STARTED'),
                        (2, 'SUCCESS'),
                        (3, 'FAILURE')
                    ],
                    default=0)),
            ],
            options={
                'unique_together': {('username', 'name')},
            },
            bases=(models.Model, lico.core.contrib.models.ToDictMixin),
        ),
        migrations.CreateModel(
            name='SingularityImageTag',
            fields=[
                ('id', models.AutoField(
                    auto_created=True,
                    primary_key=True,
                    serialize=False,
                    verbose_name='ID')
                 ),
                ('name', models.TextField()),
                ('index', models.IntegerField()),
                ('image', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='tags',
                    to='singularity.SingularityImage')
                 ),
            ],
            options={
                'abstract': False,
                'unique_together': {('image', 'index')},
            },
            bases=(models.Model, lico.core.contrib.models.ToDictMixin),
        ),
    ]
