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

from django.db import migrations, models
import django.db.models.deletion
import lico.core.contrib.fields
import lico.core.contrib.models


class Migration(migrations.Migration):

    dependencies = [
        ('job', '0001_lico_job_1_0_0'),
    ]

    operations = [
        migrations.AddField(
            model_name='job',
            name='user_comment',
            field=models.TextField(blank=True, default='', null=True),
        ),
        migrations.CreateModel(
            name='Tag',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=24)),
                ('username', models.CharField(max_length=32)),
                ('count', models.IntegerField(blank=True, default=0)),
                ('create_time', lico.core.contrib.fields.DateTimeField(auto_now_add=True)),
                ('update_time', lico.core.contrib.fields.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['jobtags__create_time'],
                'unique_together': {('name', 'username')},
            },
            bases=(models.Model, lico.core.contrib.models.ToDictMixin),
        ),
        migrations.CreateModel(
            name='JobTags',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('create_time', lico.core.contrib.fields.DateTimeField(auto_now_add=True)),
                ('update_time', lico.core.contrib.fields.DateTimeField(auto_now=True)),
                ('job', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='job.Job')),
                ('tag', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='job.Tag')),
            ],
            options={
                'unique_together': {('job', 'tag')},
            },
            bases=(models.Model, lico.core.contrib.models.ToDictMixin),
        ),
        migrations.AddField(
            model_name='job',
            name='tags',
            field=models.ManyToManyField(through='job.JobTags', to='job.Tag'),
        ),
    ]
