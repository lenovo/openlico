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
        ('oneapi', '0001_lico_oneapi_1_0_0'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='vtuneprofilewebportal',
            name='work_load_job',
        ),
        migrations.AddField(
            model_name='vtuneprofilewebportal',
            name='work_load_job_id',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='vtuneprofilewebportal',
            name='work_load_platform_id',
            field=models.IntegerField(null=True),
        ),
    ]
