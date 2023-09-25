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


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('job', '0002_lico_job_1_1_0'),
    ]

    operations = [
        migrations.CreateModel(
            name='VtuneProfileWebPortal',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True,
                                        serialize=False, verbose_name='ID')),
                ('vtune_job_id', models.IntegerField(null=True)),
                ('username', models.CharField(max_length=32)),
                ('create_time', lico.core.contrib.fields.DateTimeField(
                    auto_now_add=True)),
                ('update_time', lico.core.contrib.fields.DateTimeField(
                    auto_now=True)),
                ('work_load_job', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='vtune_profile_web_portal', to='job.Job')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, lico.core.contrib.models.ToDictMixin),
        ),
    ]
