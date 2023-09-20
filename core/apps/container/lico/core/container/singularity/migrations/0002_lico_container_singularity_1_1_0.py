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
import django.utils.timezone
import jsonfield.fields
from django.db import migrations, models

import lico.core.contrib.fields
import lico.core.contrib.models


class Migration(migrations.Migration):

    dependencies = [
        ('singularity', '0001_lico_container_singularity_1_0_0'),
    ]

    operations = [
        migrations.CreateModel(
            name='CustomImage',
            fields=[
                ('id', models.AutoField(
                    auto_created=True,
                    primary_key=True,
                    serialize=False,
                    verbose_name='ID')
                 ),
                ('name', models.CharField(max_length=100)),
                ('username', models.CharField(max_length=128, unique=True)),
                ('source', models.IntegerField(
                    choices=[(1, 1), (2, 2), (3, 3), (4, 4), (5, 5)])
                 ),
                ('workspace', models.CharField(max_length=255)),
                ('log_file', models.CharField(max_length=255)),
                ('job_id', models.CharField(max_length=128)),
                ('create_time', lico.core.contrib.fields.DateTimeField(
                    default=django.utils.timezone.now)
                 ),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, lico.core.contrib.models.ToDictMixin),
        ),
        migrations.CreateModel(
            name='CustomInfo',
            fields=[
                ('id', models.AutoField(
                    auto_created=True,
                    primary_key=True,
                    serialize=False,
                    verbose_name='ID')
                 ),
                ('key', models.CharField(max_length=100)),
                ('value', jsonfield.fields.JSONCharField(max_length=566)),
                ('image', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='custom_info',
                    to='singularity.CustomImage')
                 ),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, lico.core.contrib.models.ToDictMixin),
        ),
    ]
