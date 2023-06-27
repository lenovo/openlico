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

from django.db.models import CharField, IntegerField, TextField

from lico.core.contrib.fields import DateTimeField
from lico.core.contrib.models import Model


class UserTemplate(Model):
    index = IntegerField(null=False, default=99999)
    name = CharField(null=False, max_length=32)
    logo = TextField()
    desc = CharField(max_length=512, default='')
    parameters_json = TextField(null=False)
    template_file = TextField(null=False)
    type = CharField(max_length=32, default='')
    category = CharField(max_length=128, default='General')
    username = CharField(max_length=128, default='')
    scheduler = CharField(max_length=32, default='')
    feature_code = CharField(max_length=32, default='')
    create_time = DateTimeField(auto_now_add=True)
    update_time = DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('name', 'username')


class FavoriteTemplate(Model):
    username = CharField(max_length=128, default='')
    type = CharField(null=False, max_length=20, blank=True, default="")
    code = CharField(null=False, max_length=128, blank=True, default="")
    create_time = DateTimeField(auto_now_add=True)
    update_time = DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('username', 'code')
