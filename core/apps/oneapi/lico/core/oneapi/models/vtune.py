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

from django.db.models import CharField, IntegerField

from lico.core.contrib.fields import DateTimeField
from lico.core.contrib.models import Model


class VtuneProfileWebPortal(Model):
    work_load_job_id = IntegerField(null=True)
    work_load_platform_id = IntegerField(null=True)
    vtune_job_id = IntegerField(null=True)
    username = CharField(max_length=32)
    create_time = DateTimeField(auto_now_add=True)
    update_time = DateTimeField(auto_now=True)
