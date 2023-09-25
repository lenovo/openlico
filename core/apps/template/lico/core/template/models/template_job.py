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

from django.db.models import CharField, IntegerField, TextField

from lico.core.contrib.fields import DateTimeField
from lico.core.contrib.models import Model


class TemplateJob(Model):
    job_id = IntegerField(unique=True)
    template_code = CharField(null=False, max_length=128)
    json_body = TextField(null=False, blank=True, default="")
    username = CharField(max_length=128)
    create_time = DateTimeField(auto_now_add=True)
