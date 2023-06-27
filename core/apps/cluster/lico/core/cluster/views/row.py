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

from ..models import Node, Room, Row


class RowsView(APIView):
    permission_classes = (AsOperatorRole,)

    def get(self, request):
        return Response({
            'rows': Row.objects.as_dict(
                inspect_related=False
            )
        })


class RowDetailView(APIView):
    permission_classes = (AsOperatorRole,)

    def get(self, request, name):
        row = Row.objects.get(name=name)
        row_dict = row.as_dict(inspect_related=False)
        racks = row.racks.as_dict(
            inspect_related=False
        )
        row_dict.update(
            total_racks=len(racks),
            racks=racks,
            total_nodes=Node.objects.filter(
                rack__row=row
            ).count()
        )
        return Response(row_dict)


class RowRacksList(InternalAPIView):
    def get(self, request):
        return Response({
            'rows': Row.objects.as_dict(
                include=['name', 'racks'],
                inspect_related=True,
                related_field_options=dict(
                    racks=dict(
                        include=['name'],
                        inspect_related=False
                    )
                )
            )
        })


class RowInternalDetailView(InternalAPIView):

    def get(self, request, name):
        try:
            row = Row.objects.get(name=name)
        except Row.DoesNotExist:
            return Response({})
        else:
            return Response(row.as_dict())

    def delete(self, request, name):
        try:
            row = Row.objects.get(name=name)
            row.delete()
        except Row.DoesNotExist:
            return Response({})
        except ProtectedError as e:
            raise Exception(
                f"Can't delete row: {name}"
            ) from e
        else:
            return Response(row.as_dict())


class RowInternalAddView(InternalAPIView):

    @json_schema_validate({
        'type': 'object',
        'properties': {
            'name': {
                'type': 'string',
                'minLength': 1
            },
            'index': {
                "type": "integer",
                "minimum": 1
            },
            'room': {
                'type': 'string',
                'minLength': 1
            },
            'on_cloud': {
                'type': 'boolean'
            }
        },
        'required': ['name', 'index']
    })
    def post(self, request):
        kwargs = {
            "name": request.data['name'],
            "index": request.data['index'],
            "on_cloud": request.data.get("on_cloud", True)
        }
        room = request.data.get('room')
        if room:
            query_room = Room.objects.filter(name=room)
            if query_room:
                kwargs.update(room=query_room.first())
        try:
            row = Row.objects.create(**kwargs)
        except IntegrityError as e:
            raise Exception(
                f"The row named {request.date['name']} already exists"
            ) from e
        else:
            return Response(row.as_dict())
