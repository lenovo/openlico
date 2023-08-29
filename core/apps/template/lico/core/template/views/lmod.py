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

from rest_framework.response import Response

from lico.core.contrib.schema import json_schema_validate
from lico.core.contrib.views import APIView

from ..models import Module
from ..utils.lmod import verify_modules


class ModuleListView(APIView):
    def get(self, request):
        return Response([
            {
                'name': module.name,
                'items': [
                    {
                        'name': item.name,
                        'version': item.version,
                        'path': item.path,
                        'category': item.category,
                        'description': item.description,
                        'parents': item.parents_list

                    }
                    for item in module.items.iterator()
                ]
            }
            for module in Module.objects.order_by(
                'name'
            ).iterator()
        ])


class ModuleVerifyView(APIView):
    @json_schema_validate({
        'type': 'object',
        'properties': {
            'modules': {
                'type': 'array',
                'items': {
                    'type': 'string',
                    'minLength': 1,
                },
                'minItems': 1
            }
        },
        'required': [
            'modules'
        ]
    })
    def post(self, request):
        verify_modules(
            user=request.user,
            modules=request.data['modules']
        )

        return Response()
