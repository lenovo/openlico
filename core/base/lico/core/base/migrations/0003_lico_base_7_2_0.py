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
        ('base', '0002_lico_secret_key'),
    ]

    operations = [
        migrations.AlterField(
            model_name='operationlog',
            name='operation',
            field=models.CharField(
                choices=[
                    ('create', 'create'),
                    ('update', 'update'),
                    ('delete', 'delete'),
                    ('recharge', 'recharge'),
                    ('chargeback', 'chargeback'),
                    ('solve', 'solve'),
                    ('confirm', 'confirm'),
                    ('turn_on', 'turn_on'),
                    ('turn_off', 'turn_off'),
                    ('cancel', 'cancel'),
                    ('hold', 'hold'),
                    ('release', 'release'),
                    ('suspend', 'suspend'),
                    ('resume', 'resume'),
                    ('rerun', 'rerun'),
                    ('comment', 'comment'),
                    ('priority', 'priority'),
                    ('requeue', 'requeue'),
                    ('low_balance', 'low_balance')
                ], max_length=128),
        ),
    ]
