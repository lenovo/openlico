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
    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='HeartBeat',
            fields=[
                ('uuid', models.CharField(
                    max_length=64, primary_key=True, serialize=False)
                 ),
                ('recent_time', lico.core.contrib.fields.DateTimeField(
                    auto_now_add=True)
                 ),
                ('job_id', models.IntegerField(null=True)),
                ('train_dir', models.TextField()),
                ('port', models.IntegerField()),
                ('username', models.CharField(max_length=32)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, lico.core.contrib.models.ToDictMixin),
        ),
    ]
