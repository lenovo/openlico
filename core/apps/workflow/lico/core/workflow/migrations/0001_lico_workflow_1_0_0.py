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
            name='Workflow',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True,
                                        serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128)),
                ('owner', models.CharField(max_length=32)),
                ('run_policy', models.CharField(
                    choices=[('ignore_failed', 'ignore_failed'),
                             ('all_completed', 'all_completed')],
                    default='all_completed', max_length=32)),
                ('max_submit_jobs', models.IntegerField(default=3)),
                ('status', models.CharField(blank=True,
                                            choices=[
                                                ('created', 'created'),
                                                ('starting', 'starting'),
                                                ('cancelling', 'cancelling'),
                                                ('completed', 'completed'),
                                                ('failed', 'failed'),
                                                ('cancelled', 'cancelled')],
                                            max_length=32, null=True)),
                ('create_time',
                 lico.core.contrib.fields.DateTimeField(auto_now_add=True)),
                ('update_time',
                 lico.core.contrib.fields.DateTimeField(auto_now=True)),
                ('start_time',
                 lico.core.contrib.fields.DateTimeField(null=True)),
                ('description', models.TextField(null=True)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, lico.core.contrib.models.ToDictMixin),
        ),
        migrations.CreateModel(
            name='WorkflowStep',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True,
                                        serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128)),
                ('order', models.IntegerField()),
                ('create_time',
                 lico.core.contrib.fields.DateTimeField(auto_now_add=True)),
                ('update_time',
                 lico.core.contrib.fields.DateTimeField(auto_now=True)),
                ('description', models.TextField(null=True)),
                ('workflow',
                 models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                   related_name='workflow_steps',
                                   to='workflow.Workflow')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, lico.core.contrib.models.ToDictMixin),
        ),
        migrations.CreateModel(
            name='WorkflowStepJob',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True,
                                        serialize=False, verbose_name='ID')),
                ('job_name', models.CharField(max_length=128)),
                ('job_id', models.IntegerField(null=True)),
                ('template_id', models.CharField(max_length=128)),
                ('create_time',
                 lico.core.contrib.fields.DateTimeField(auto_now_add=True)),
                ('update_time',
                 lico.core.contrib.fields.DateTimeField(auto_now=True)),
                ('json_body', jsonfield.fields.JSONField()),
                ('workflow_step',
                 models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                   related_name='step_job',
                                   to='workflow.WorkflowStep')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, lico.core.contrib.models.ToDictMixin),
        ),
    ]
