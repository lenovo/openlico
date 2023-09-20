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
            name='Project',
            fields=[
                (
                    'id', models.AutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name='ID'
                    )
                ),
                ('name', models.CharField(max_length=128)),
                ('username', models.CharField(default='', max_length=128)),
                ('workspace', models.CharField(
                    blank=True, default='', max_length=512
                )),
                ('environment', models.CharField(
                    default='MyFolder/.lico_env', max_length=512
                )),
                ('settings', jsonfield.fields.JSONField(null=True)),
                ('create_time', lico.core.contrib.fields.DateTimeField(
                    auto_now_add=True
                )),
                ('update_time', lico.core.contrib.fields.DateTimeField(
                    auto_now=True
                )),
            ],
            options={
                'unique_together': {('name', 'username')},
            },
            bases=(models.Model, lico.core.contrib.models.ToDictMixin),
        ),
        migrations.CreateModel(
            name='Tool',
            fields=[
                ('id', models.AutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID')
                 ),
                ('name', models.CharField(max_length=128)),
                ('code', models.CharField(max_length=128, unique=True)),
                ('job_template', models.CharField(max_length=128)),
                ('setting_params', models.CharField(max_length=512)),
                ('create_time', lico.core.contrib.fields.DateTimeField(
                    auto_now_add=True)
                 ),
                ('update_time', lico.core.contrib.fields.DateTimeField(
                    auto_now=True)
                 ),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, lico.core.contrib.models.ToDictMixin),
        ),
        migrations.CreateModel(
            name='ToolInstance',
            fields=[
                (
                    'id', models.AutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name='ID'
                    )
                ),
                ('job', models.IntegerField()),
                ('template_job', models.IntegerField()),
                ('entrance_uri', models.CharField(max_length=512, null=True)),
                ('create_time', lico.core.contrib.fields.DateTimeField(
                    auto_now_add=True
                )),
                ('update_time', lico.core.contrib.fields.DateTimeField(
                    auto_now=True
                )),
                ('project', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='project_instances',
                    to='cloudtools.Project'
                )),
                ('tool', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='tool_instances', to='cloudtools.Tool'
                )),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, lico.core.contrib.models.ToDictMixin),
        ),
        migrations.CreateModel(
            name='ToolSetting',
            fields=[
                ('id', models.AutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID')
                 ),
                ('settings', jsonfield.fields.JSONField()),
                ('existing_env', models.CharField(default='', max_length=512)),
                ('is_initialized', models.BooleanField(default=True)),
                ('create_time', lico.core.contrib.fields.DateTimeField(
                    auto_now_add=True
                )),
                ('update_time', lico.core.contrib.fields.DateTimeField(
                    auto_now=True
                )),
                ('project', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='project_settings', to='cloudtools.Project')
                 ),
                ('tool', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='tool_settings', to='cloudtools.Tool'
                )),
            ],
            options={
                'unique_together': {('tool', 'project')},
            },
            bases=(models.Model, lico.core.contrib.models.ToDictMixin),
        ),
        migrations.CreateModel(
            name='ToolSharing',
            fields=[
                ('id', models.AutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID'
                )),
                ('sharing_uuid', models.CharField(max_length=100)),
                ('project', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='project_sharing', to='cloudtools.Project'
                )),
                ('tool', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='tool_sharing', to='cloudtools.Tool'
                )),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, lico.core.contrib.models.ToDictMixin),
        )
    ]
