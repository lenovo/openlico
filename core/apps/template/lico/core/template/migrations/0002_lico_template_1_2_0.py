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


class Migration(migrations.Migration):

    dependencies = [
        ('template', '0001_lico_template_1_0_0'),
    ]

    operations = [
        migrations.AddField(
            model_name='runtime',
            name='tag',
            field=models.CharField(default='', max_length=255),
        ),
        migrations.AddField(
            model_name='runtime',
            name='type',
            field=models.CharField(default='Runtime', max_length=20),
        ),
        migrations.AlterUniqueTogether(
            name='runtime',
            unique_together={('name', 'username', 'type')},
        ),
    ]
