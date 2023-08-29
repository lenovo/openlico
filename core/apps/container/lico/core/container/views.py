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

from abc import ABCMeta, abstractmethod

from rest_framework.response import Response

from lico.core.contrib.schema import json_schema_validate
from lico.core.contrib.views import InternalAPIView


class SearchImageListView(InternalAPIView, metaclass=ABCMeta):

    @json_schema_validate({
        'type': 'object',
        'properties': {
            'image_name': {
                'type': 'string',
                'minLength': 1,
            },
            'framework': {
                'type': 'string',
                'minLength': 1,
            },
            'tags': {
                "type": "array",
                'items': {
                    "type": "string"
                },
            }
        },
    })
    def post(self, request):
        image_name = request.data.get('image_name')
        framework = request.data.get('framework')
        tags = request.data.get('tags', [])
        images = self.get_images()
        if image_name:
            images = images.filter(name=image_name)
        if framework:
            images = images.filter(framework=framework)
        if tags:
            for tag in tags:
                images = images.filter(tags__name=tag)
        return Response(
            {
                "images": images.order_by("-create_time").as_dict(
                    include=[
                        'name', 'image_path', 'framework',
                        'tags', 'version'
                    ],
                    related_field_options=dict(
                        tags=dict(
                            include=['name'],
                            inspect_related=False
                        )
                    )
                )
            }
        )

    @abstractmethod
    def get_images(self):
        pass
