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

import jsonfield.fields
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('alert', '0003_lico_core_alert_1_2_0'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='policy',
            name='sms',
        ),
        migrations.RemoveField(
            model_name='policy',
            name='wechat',
        ),
        migrations.AddField(
            model_name='policy',
            name='comments',
            field=jsonfield.fields.JSONField(default=[]),
        )
    ]
