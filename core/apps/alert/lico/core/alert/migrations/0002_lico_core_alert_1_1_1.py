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
        ('alert', '0001_lico_core_alert_1_0_0'),
    ]

    operations = [
        migrations.AlterField(
            model_name='policy',
            name='metric_policy',
            field=models.CharField(
                choices=[('CPUSAGE', 'cpusage'),
                         ('MEMORY_UTIL', 'memory_util'),
                         ('TEMP', 'tempature'),
                         ('NETWORK', 'network'),
                         ('DISK', 'disk'),
                         ('ELECTRIC', 'electric'),
                         ('NODE_ACTIVE', 'node_active'),
                         ('HARDWARE', 'hardware'),
                         ('GPU_UTIL', 'gpu_util'),
                         ('GPU_TEMP', 'gpu_temp'),
                         ('GPU_MEM', 'gpu_mem')],
                max_length=20,
                null=True),
        ),
    ]
