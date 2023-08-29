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

from lico.core.contrib.permissions import AsOperatorRole
from lico.core.contrib.schema import json_schema_validate
from lico.core.contrib.views import APIView, InternalAPIView

from ..models import Node, NodeGroup


class NodeGroupView(APIView):
    permission_classes = (AsOperatorRole,)

    def get(self, request):
        return Response({
            'groups': NodeGroup.objects.as_dict(
                inspect_related=False
            )
        })


class NodeGroupHostList(InternalAPIView):
    def get(self, request):
        return Response({
            'groups': NodeGroup.objects.as_dict(
                include=['name', 'on_cloud', 'nodes'],
                inspect_related=True,
                related_field_options=dict(
                    nodes=dict(
                        include=['hostname', 'type', 'on_cloud'],
                        inspect_related=False
                    )
                )
            )
        })


class NodegroupInternalDetailView(InternalAPIView):

    def get(self, request, name):
        try:
            group = NodeGroup.objects.get(name=name)
        except NodeGroup.DoesNotExist:
            return Response({})
        else:
            return Response(group.as_dict(
                include=['name', 'on_cloud', 'nodes'],
                inspect_related=True,
                related_field_options=dict(
                    nodes=dict(
                        include=['hostname', 'type', 'on_cloud'],
                        inspect_related=False
                    )
                )
            ))

    def delete(self, request, name):
        try:
            NodeGroup.objects.get(name=name).delete()
        except NodeGroup.DoesNotExist:
            return Response({})
        else:
            return Response({"name": name})


class NodeGroupInternalAddView(InternalAPIView):
    @json_schema_validate({
        'type': 'object',
        'properties': {
            'name': {
                'type': 'string',
                'minLength': 1
            },
            'nodes': {
                "type": "array",
                "items": {
                    "type": "string"
                },
                "minItems": 1
            },
            'on_cloud': {
                'type': 'boolean'
            }
        },
        'required': ['name', 'nodes']
    })
    def post(self, request):
        group, _ = NodeGroup.objects.update_or_create(
            name=request.data['name'],
            defaults={"on_cloud": request.data.get("on_cloud", True)}
        )
        nodes = Node.objects.filter(hostname__in=request.data['nodes'])
        group.nodes.set(nodes)
        return Response(group.as_dict(
            include=['name', 'on_cloud', 'nodes'],
            inspect_related=True,
            related_field_options=dict(
                nodes=dict(
                    include=['hostname', 'type', 'on_cloud'],
                    inspect_related=False
                )
            )
        ))
