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

from django.db import IntegrityError
from django.db.models.deletion import ProtectedError
from rest_framework.response import Response

from lico.core.contrib.permissions import AsOperatorRole
from lico.core.contrib.schema import json_schema_validate
from lico.core.contrib.views import APIView, InternalAPIView

from ..models import Rack, Room, Row


class RackDetailView(APIView):
    permission_classes = (AsOperatorRole,)

    def get(self, request, name):
        return Response(
            Rack.objects.get(name=name).as_dict(
                inspect_related=True
            )
        )


class RackView(APIView):
    permission_classes = (AsOperatorRole,)

    def get(self, request):
        return Response(
            {
                'racks': Rack.objects.as_dict(
                    inspect_related=False,
                    include=["id", "name", "col", "on_cloud"]
                )
            }
        )


class RackHostList(InternalAPIView):
    @json_schema_validate({
        "type": "object",
        "properties": {
            "racks": {
                "type": "array",
                "items": {
                    "type": "string"
                }
            }
        },
        "required": ["racks"]
    })
    def post(self, request):
        query = Rack.objects
        racks = request.data.get('racks')
        if racks:
            query = query.filter(name__in=racks)
        return Response({
            'racks': query.as_dict(
                include=['name', 'nodes'],
                inspect_related=True,
                related_field_options=dict(
                    nodes=dict(
                        include=['hostname', 'type', 'on_cloud'],
                        inspect_related=False
                    )
                )
            )
        })


class RackHierarchyView(APIView):
    permission_classes = (AsOperatorRole,)

    def get(self, request):
        data = Room.objects.as_dict(
            include=['id', 'name', 'rows'],
            inspect_related=True,
            related_field_options=dict(
                rows=dict(
                    include=['id', 'name', 'racks'],
                    inspect_related=True,
                    related_field_options=dict(
                        racks=dict(
                            include=['name', 'id'],
                            inspect_related=False
                        )
                    )
                )
            )
        )

        return Response({"data": data})


class RackInternalDetailView(InternalAPIView):

    def get(self, request, name):
        try:
            rack = Rack.objects.get(name=name)
        except Rack.DoesNotExist:
            return Response({})
        else:
            return Response(rack.as_dict())

    def delete(self, request, name):
        try:
            rack = Rack.objects.get(name=name)
            rack.delete()
        except Rack.DoesNotExist:
            return Response({})
        except ProtectedError as e:
            raise Exception(
                f"Can't delete rack: {name}"
            ) from e
        else:
            return Response(rack.as_dict())


class RackInternalAddView(InternalAPIView):

    @json_schema_validate({
        'type': 'object',
        'properties': {
            'name': {
                'type': 'string',
                'minLength': 1
            },
            'col': {
                "type": "integer",
                "minimum": 1
            },
            'row': {
                'type': 'string',
                'minLength': 1
            },
            'on_cloud': {
                'type': 'boolean'
            }
        },
        'required': ['name', 'col']
    })
    def post(self, request):
        kwargs = {
            "name": request.data['name'],
            "col": request.data['col'],
            "on_cloud": request.data.get("on_cloud", True)
        }
        row = request.data.get('row')
        if row:
            query_row = Row.objects.filter(name=row)
            if query_row:
                kwargs.update(row=query_row.first())
        try:
            rack = Rack.objects.create(**kwargs)
        except IntegrityError as e:
            raise Exception(
                f"The rack named {request.data['name']} already exists"
            ) from e
        else:
            return Response(rack.as_dict())
