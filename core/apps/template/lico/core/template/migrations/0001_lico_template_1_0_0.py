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
            name='JobComp',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('job', models.IntegerField()),
                ('url', models.TextField(null=True)),
                ('type', models.CharField(max_length=20)),
                ('triggered', models.BooleanField(default=False)),
                ('method', models.CharField(default='POST', max_length=20)),
                ('notice_type', models.CharField(choices=[('rest', 'restapi'), ('email', 'email')], default='rest', max_length=20)),
                ('create_time', lico.core.contrib.fields.DateTimeField(auto_now_add=True)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, lico.core.contrib.models.ToDictMixin),
        ),
        migrations.CreateModel(
            name='Module',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, unique=True)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, lico.core.contrib.models.ToDictMixin),
        ),
        migrations.CreateModel(
            name='Runtime',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128)),
                ('create_time', lico.core.contrib.fields.DateTimeField(auto_now_add=True)),
                ('username', models.CharField(default='', max_length=128)),
            ],
            options={
                'unique_together': {('name', 'username')},
            },
            bases=(models.Model, lico.core.contrib.models.ToDictMixin),
        ),
        migrations.CreateModel(
            name='Template',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('index', models.IntegerField(default=99999)),
                ('code', models.CharField(max_length=128, unique=True)),
                ('name', models.CharField(max_length=128)),
                ('category', models.CharField(max_length=128)),
                ('feature_code', models.CharField(max_length=128)),
                ('type', models.CharField(max_length=128)),
                ('description', models.TextField(null=True)),
                ('enable', models.BooleanField(default=True)),
                ('backend', models.CharField(default='common', max_length=128)),
                ('display', models.BooleanField(default=True)),
                ('subtemplate', models.TextField(null=True)),
                ('location', models.TextField()),
                ('params', models.TextField(null=True)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, lico.core.contrib.models.ToDictMixin),
        ),
        migrations.CreateModel(
            name='TemplateJob',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('job_id', models.IntegerField(unique=True)),
                ('template_code', models.CharField(max_length=128)),
                ('json_body', models.TextField(blank=True, default='')),
                ('username', models.CharField(max_length=128)),
                ('create_time', lico.core.contrib.fields.DateTimeField(auto_now_add=True)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, lico.core.contrib.models.ToDictMixin),
        ),
        migrations.CreateModel(
            name='UserTemplate',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=32)),
                ('logo', models.TextField()),
                ('desc', models.CharField(default='', max_length=512)),
                ('parameters_json', models.TextField()),
                ('template_file', models.TextField()),
                ('type', models.CharField(default='', max_length=32)),
                ('category', models.CharField(default='', max_length=128)),
                ('username', models.CharField(default='', max_length=128)),
                ('scheduler', models.CharField(default='', max_length=32)),
                ('feature_code', models.CharField(default='', max_length=32)),
                ('create_time', lico.core.contrib.fields.DateTimeField(auto_now_add=True)),
                ('update_time', lico.core.contrib.fields.DateTimeField(auto_now=True)),
            ],
            options={
                'unique_together': {('name', 'username')},
            },
            bases=(models.Model, lico.core.contrib.models.ToDictMixin),
        ),
        migrations.CreateModel(
            name='ModuleItem',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('version', models.CharField(max_length=255, null=True)),
                ('path', models.CharField(max_length=255, unique=True)),
                ('category', models.CharField(max_length=255, null=True)),
                ('description', models.CharField(max_length=255, null=True)),
                ('parents', models.CharField(max_length=255, null=True)),
                ('module', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='template.Module')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, lico.core.contrib.models.ToDictMixin),
        ),
        migrations.CreateModel(
            name='FavoriteTemplate',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('username', models.CharField(default='', max_length=128)),
                ('type', models.CharField(blank=True, default='', max_length=20)),
                ('code', models.CharField(blank=True, default='', max_length=128)),
                ('create_time', lico.core.contrib.fields.DateTimeField(auto_now_add=True)),
                ('update_time', lico.core.contrib.fields.DateTimeField(auto_now=True)),
            ],
            options={
                'unique_together': {('username', 'code')},
            },
            bases=(models.Model, lico.core.contrib.models.ToDictMixin),
        ),
        migrations.CreateModel(
            name='RuntimeModule',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('module', models.CharField(max_length=255)),
                ('parents', models.CharField(max_length=255, null=True)),
                ('index', models.IntegerField()),
                ('runtime', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='modules', to='template.Runtime')),
            ],
            options={
                'unique_together': {('runtime', 'index')},
            },
            bases=(models.Model, lico.core.contrib.models.ToDictMixin),
        ),
        migrations.CreateModel(
            name='RuntimeEnv',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('value', models.TextField()),
                ('index', models.IntegerField()),
                ('runtime', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='envs', to='template.Runtime')),
            ],
            options={
                'unique_together': {('runtime', 'name')},
            },
            bases=(models.Model, lico.core.contrib.models.ToDictMixin),
        ),
    ]
