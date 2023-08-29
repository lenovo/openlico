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

from lico.core.contrib.models import ToDictMixin


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('cluster', '0001_lico_cluster_1_0_0'),
    ]

    operations = [
        migrations.CreateModel(
            name='Asyncid',
            fields=[
                ('id', models.AutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID'
                )),
                ('asyncid', models.CharField(max_length=32)),
                ('sessionid', models.CharField(max_length=32)),
                ('ipaddr', models.CharField(max_length=32)),
                ('session', models.CharField(max_length=32, null=True)),
                ('create_time', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, ToDictMixin),
        ),
    ]
