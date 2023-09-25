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

from django.db.models import CASCADE, CharField, ForeignKey, IntegerField
from django.db.models.fields import BooleanField

from lico.core.contrib.fields import DateTimeField, JSONField
from lico.core.contrib.models import Model


class Project(Model):
    name = CharField(max_length=128, null=False)
    username = CharField(max_length=128, default="")
    workspace = CharField(max_length=512, null=False, blank=True, default="")
    environment = CharField(max_length=512, default="MyFolder/.lico_env")
    # Placeholder for add project settings
    settings = JSONField(null=True)
    create_time = DateTimeField(auto_now_add=True)
    update_time = DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("name", "username")


class Tool(Model):
    name = CharField(null=False, max_length=128)
    code = CharField(null=False, max_length=128, unique=True)
    # name for job template
    job_template = CharField(null=False, max_length=128)
    # the key from job template params
    setting_params = CharField(null=False, max_length=512)
    create_time = DateTimeField(auto_now_add=True)
    update_time = DateTimeField(auto_now=True)


class ToolSetting(Model):
    tool = ForeignKey(
        Tool, blank=False, on_delete=CASCADE,
        related_name="tool_settings"
    )
    project = ForeignKey(
        Project, blank=False, on_delete=CASCADE,
        related_name="project_settings"
    )
    existing_env = CharField(max_length=512, default="")
    settings = JSONField(null=False)
    is_initialized = BooleanField(default=True)
    create_time = DateTimeField(auto_now_add=True)
    update_time = DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("tool", "project")


class ToolInstance(Model):
    tool = ForeignKey(
        Tool, blank=False, on_delete=CASCADE,
        related_name="tool_instances"
    )
    project = ForeignKey(
        Project, blank=False, on_delete=CASCADE,
        related_name="project_instances"
    )
    job = IntegerField(null=False)
    template_job = IntegerField(null=False)
    entrance_uri = CharField(max_length=512, null=True)
    create_time = DateTimeField(auto_now_add=True)
    update_time = DateTimeField(auto_now=True)


class ToolSharing(Model):
    tool = ForeignKey(
        Tool, blank=False, on_delete=CASCADE,
        related_name="tool_sharing"
    )
    project = ForeignKey(
        Project, blank=False, on_delete=CASCADE,
        related_name="project_sharing"
    )
    sharing_uuid = CharField(max_length=100, null=False)
