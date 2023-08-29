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

from ..models import Node, Room


class RoomView(APIView):
    permission_classes = (AsOperatorRole,)

    def get(self, request):
        return Response({
            'rooms': [
                self.get_statics(room)
                for room in Room.objects.iterator()
            ]
        })

    @staticmethod
    def get_statics(room):
        node_num = Node.objects.filter(
            rack__row__room=room
        ).count()
        return {
            'id': room.id,
            'name': room.name,
            'location': room.location,
            'node_num': node_num,
            "on_cloud": room.on_cloud
        }


class RoomInternalDetailView(InternalAPIView):

    def get(self, request, name):
        try:
            room = Room.objects.get(name=name)
        except Room.DoesNotExist:
            return Response({})
        else:
            return Response(room.as_dict())

    def delete(self, request, name):
        try:
            room = Room.objects.get(name=name)
            room.delete()
        except Room.DoesNotExist:
            return Response({})
        except ProtectedError as e:
            raise Exception(
                f"Can't delete room: {name}"
            ) from e
        else:
            return Response(room.as_dict())


class RoomInternalAddView(InternalAPIView):
    @json_schema_validate({
        'type': 'object',
        'properties': {
            'name': {
                'type': 'string',
                'minLength': 1
            },
            'location': {
                'type': 'string',
                'minLength': 1
            },
            'on_cloud': {
                'type': 'boolean'
            }
        },
        'required': ['name', 'location']
    })
    def post(self, request):
        try:
            room = Room.objects.create(
                name=request.data['name'],
                location=request.data['location'],
                on_cloud=request.data.get('on_cloud', True)
            )
        except IntegrityError as e:
            raise Exception(
                f"The room named {request.date['name']} already exists"
            ) from e
        else:
            return Response(room.as_dict())
