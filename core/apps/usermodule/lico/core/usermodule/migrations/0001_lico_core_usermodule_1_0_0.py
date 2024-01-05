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
            name='UserModuleJob',
            fields=[
                ('id', models.AutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID'
                )),
                ('job_id', models.IntegerField(unique=True)),
                ('software_name', models.CharField(max_length=256)),
                ('is_cleared', models.BooleanField(blank=True, default=False)),
                ('user', models.CharField(
                    blank=True, default='', max_length=32
                )),
                ('create_time', lico.core.contrib.fields.DateTimeField(
                    auto_now_add=True, db_index=True
                )),
                ('update_time', lico.core.contrib.fields.DateTimeField(
                    auto_now=True
                )),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, lico.core.contrib.models.ToDictMixin),
        ),
    ]
