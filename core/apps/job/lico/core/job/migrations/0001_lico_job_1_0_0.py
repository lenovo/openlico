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


class Migration(migrations.Migration):  # pragma: no cover

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Job',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('scheduler_id', models.CharField(blank=True, db_index=True, default='', max_length=64)),
                ('identity_str', models.TextField(blank=True, default='')),
                ('job_name', models.CharField(blank=True, default='', max_length=128)),
                ('job_content', models.TextField(blank=True, default='')),
                ('queue', models.CharField(blank=True, default='', max_length=128)),
                ('submit_time', lico.core.contrib.fields.DateTimeField(auto_now_add=True)),
                ('start_time', lico.core.contrib.fields.DateTimeField(blank=True, null=True)),
                ('end_time', lico.core.contrib.fields.DateTimeField(blank=True, null=True)),
                ('submitter', models.CharField(blank=True, default='', max_length=32)),
                ('job_file', models.CharField(blank=True, default='', max_length=260)),
                ('workspace', models.CharField(blank=True, default='', max_length=260)),
                ('scheduler_state', models.CharField(blank=True, default='', max_length=24)),
                ('state', models.CharField(blank=True, default='', max_length=24)),
                ('operate_state', models.CharField(blank=True, default='', max_length=24)),
                ('delete_flag', models.BooleanField(blank=True, default=False)),
                ('runtime', models.IntegerField(blank=True, default=0)),
                ('standard_output_file', models.CharField(blank=True, default='', max_length=260)),
                ('error_output_file', models.CharField(blank=True, default='', max_length=260)),
                ('raw_info', models.TextField(blank=True, default='')),
                ('reason', models.TextField(blank=True, default='')),
                ('comment', models.CharField(blank=True, default='', max_length=256)),
                ('exit_code', models.CharField(blank=True, default='', max_length=16)),
                ('tres', models.TextField(blank=True, default='')),
                ('create_time', lico.core.contrib.fields.DateTimeField(auto_now_add=True)),
                ('update_time', lico.core.contrib.fields.DateTimeField(auto_now=True)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, lico.core.contrib.models.ToDictMixin),
        ),
        migrations.CreateModel(
            name='JobRunning',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('hosts', models.TextField(blank=True, default='')),
                ('per_host_tres', models.TextField(blank=True, default='')),
                ('job', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='job_running', to='job.Job')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, lico.core.contrib.models.ToDictMixin),
        ),
        migrations.CreateModel(
            name='JobCSRES',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('csres_code', models.CharField(blank=True, default='', max_length=16)),
                ('csres_value', models.CharField(blank=True, default='', max_length=16)),
                ('job', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='job_csres', to='job.Job')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, lico.core.contrib.models.ToDictMixin),
        ),
    ]
