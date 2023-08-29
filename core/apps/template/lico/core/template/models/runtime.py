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

from django.db.models import (
    CASCADE, CharField, ForeignKey, IntegerField, TextField,
)

from lico.core.contrib.fields import DateTimeField
from lico.core.contrib.models import Model


class Module(Model):
    name = CharField(unique=True, max_length=255)


class ModuleItem(Model):
    module = ForeignKey(
        Module, related_name='items',
        null=False, on_delete=CASCADE
    )
    name = CharField(null=False, max_length=255)
    version = CharField(null=True, max_length=255)
    path = CharField(null=False, unique=True, max_length=255)
    category = CharField(null=True, max_length=255)
    description = CharField(null=True, max_length=255)
    parents = CharField(null=True, max_length=255)

    @property
    def parents_list(self):
        return [] \
            if self.parents is None or len(self.parents) == 0 \
            else self.parents.split(',')


class Runtime(Model):
    name = CharField(null=False, max_length=128)
    tag = CharField(max_length=255, default='')
    create_time = DateTimeField(auto_now_add=True)
    username = CharField(max_length=128, default='')
    type = CharField(max_length=20, default='Runtime')  # 1.Runtime 2.Affinity

    class Meta:
        unique_together = ("name", "username", "type")

    @property
    def module_list(self):
        return [
            item.module for item in
            self.modules.order_by('index')
        ]

    @property
    def env_list(self):
        return [
            '{0.name}={0.value}'.format(item) for item in
            self.envs.order_by('index')
        ]

    @property
    def script_list(self):
        return [
            item.filename for item in
            self.scripts.order_by('index')
        ]


class RuntimeModule(Model):
    runtime = ForeignKey(
        Runtime, related_name='modules',
        null=False, on_delete=CASCADE
    )
    module = CharField(null=False, max_length=255)
    parents = CharField(null=True, max_length=255)
    index = IntegerField(null=False)

    class Meta:
        unique_together = ("runtime", "index")

    @property
    def parents_list(self):
        return [] \
            if self.parents is None or len(self.parents) == 0 \
            else self.parents.split(',')


class RuntimeEnv(Model):
    runtime = ForeignKey(
        Runtime, related_name='envs',
        null=False, on_delete=CASCADE
    )
    name = CharField(null=False, max_length=255)
    value = TextField(null=False)
    index = IntegerField(null=False)

    class Meta:
        unique_together = ("runtime", "name")


class RuntimeScript(Model):
    runtime = ForeignKey(
        Runtime, related_name='scripts',
        null=False, on_delete=CASCADE
    )
    filename = CharField(null=False, max_length=255)
    index = IntegerField(null=False)

    class Meta:
        unique_together = ("runtime", "filename")
