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

from django.db.models import CASCADE, CharField, ForeignKey, IntegerField
from django.utils import timezone

from lico.core.contrib.fields import DateTimeField, JSONCharField
from lico.core.contrib.models import Model

from ..models import Image, ImageTag
from .utils import TaskStatus


class SingularityImage(Image):
    task_status = [(i, v.name) for i, v in enumerate(TaskStatus)]
    username = CharField(max_length=32, default="")
    status = IntegerField(
        default=TaskStatus.PENDING.value, choices=task_status)

    class Meta:
        unique_together = ('username', 'name')


class SingularityImageTag(ImageTag):
    image = ForeignKey(
        SingularityImage,
        related_name="tags",
        on_delete=CASCADE
    )


class CustomImage(Model):
    DOCKER = 1
    SINGULARITY = 2
    DEFINITION = 3
    LOCALSYSTEMIMAGE = 4
    LOCALPRIVATEMIMAGE = 5

    SOURCE_CHOICES = (
        (DOCKER, 1),
        (SINGULARITY, 2),
        (DEFINITION, 3),
        (LOCALSYSTEMIMAGE, 4),
        (LOCALPRIVATEMIMAGE, 5)
    )
    name = CharField(null=False, max_length=100)
    username = CharField(null=False, max_length=128, unique=True)
    source = IntegerField(null=False, choices=SOURCE_CHOICES)
    workspace = CharField(null=False, max_length=255)
    log_file = CharField(null=False, max_length=255)
    job_id = CharField(null=False, max_length=128)
    create_time = DateTimeField(default=timezone.now)


class CustomInfo(Model):
    image = ForeignKey(
        CustomImage,
        related_name="custom_info",
        on_delete=CASCADE
    )
    key = CharField(null=False, max_length=100)
    value = JSONCharField(null=False, max_length=566)
