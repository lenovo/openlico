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

import lico.core.contrib.models


class Migration(migrations.Migration):

    dependencies = [
        ('template', '0002_lico_template_1_2_0'),
    ]

    operations = [
        migrations.CreateModel(
            name='RuntimeScript',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('filename', models.CharField(max_length=255)),
                ('index', models.IntegerField()),
                ('runtime', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='scripts', to='template.Runtime')),
            ],
            options={
                'unique_together': {('runtime', 'filename')},
            },
            bases=(models.Model, lico.core.contrib.models.ToDictMixin),
        ),
    ]
