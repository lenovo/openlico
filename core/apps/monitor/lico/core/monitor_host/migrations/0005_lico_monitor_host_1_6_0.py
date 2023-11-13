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


class Migration(migrations.Migration):
    dependencies = [
        ('monitor_host', '0004_lico_monitor_host_1_5_0'),
    ]

    operations = [
        migrations.AlterField(
            model_name='HardwareHealth',
            name='states',
            field=models.TextField(null=False, blank=True, default=''),
        ),
        migrations.AddField(
            model_name='gpu',
            name='parent_uuid',
            field=models.CharField(max_length=128, null=True),
        ),
        migrations.AddField(
            model_name='gpu',
            name='uuid',
            field=models.CharField(max_length=128, null=True),
        ),
    ]
