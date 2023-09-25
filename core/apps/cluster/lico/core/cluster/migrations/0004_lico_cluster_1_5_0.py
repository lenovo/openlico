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
        ('cluster', '0003_lico_cluster_1_4_0'),
    ]

    operations = [
        migrations.AddField(
            model_name='node',
            name='manage_method',
            field=models.CharField(
                choices=[('ipmi', 'ipmi'), ('redfish', 'redfish')],
                default=None, max_length=128, null=True),
        ),
        migrations.AddField(
            model_name='node',
            name='vendor',
            field=models.CharField(max_length=255, null=True),
        ),
    ]
