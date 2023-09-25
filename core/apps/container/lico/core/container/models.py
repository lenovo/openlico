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


class Image(Model):
    name = CharField(max_length=100)
    image_path = CharField(max_length=255, unique=True)
    description = TextField(null=True)
    framework = CharField(max_length=32)
    create_time = DateTimeField(auto_now_add=True)
    version = CharField(max_length=32, null=True)

    class Meta:
        abstract = True

    def as_dict_on_finished(self, result, is_exlucded, **kwargs):
        if 'tags' in result:
            result["tags"] = [
                item["name"] for item in result["tags"]
            ]


class ImageTag(Model):
    name = TextField()
    index = IntegerField()

    class Meta:
        abstract = True
        unique_together = ("image", "index")
