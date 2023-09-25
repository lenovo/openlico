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

import logging

from django.db import IntegrityError
from rest_framework.response import Response

from lico.core.contrib.permissions import AsOperatorRole
from lico.core.contrib.schema import json_schema_validate
from lico.core.contrib.views import APIView, DataTableView, InternalAPIView

from ..exceptions import PowerOperationException
from ..models import Chassis, Node, Rack

logger = logging.getLogger(__name__)


class NodeListView(DataTableView):
    def trans_result(self, result):
        return result.as_dict(
            include=[
                'id', 'hostname', 'type',
                'mgt_address', 'bmc_address', 'groups',
                'on_cloud'
            ],
            related_field_options=dict(
                groups=dict(
                    include=['name'],
                    inspect_related=False
                )
            )
        )

    def get_query(self, request, *args, **kwargs):
        return Node.objects


class NodeAllView(APIView):
    def get(self, request):
        query = Node.objects
        if 'type' in request.query_params:
            query = query.filter(type=request.query_params['type'])
        return Response({
            'nodes': query.as_dict(
                include=['hostname', 'type', 'on_cloud'],
                inspect_related=False
            )
        })


class NodeHostList(InternalAPIView):
    def get(self, request):
        return Response({
            'nodes': Node.objects.as_dict(
                include=['hostname', 'type', 'on_cloud'],
                inspect_related=False
            )
        })


class NodeDetailView(APIView):
    permission_classes = (AsOperatorRole,)

    def get(self, request, hostname):
        node = Node.objects.get(hostname=hostname)
        return Response(node.as_dict(
            related_field_options=dict(
                groups=dict(
                    include=['name'],
                    inspect_related=False
                )
            )
        ))

    @json_schema_validate({
        'type': 'object',
        'properties': {
            'operation': {
                'type': 'string',
                'enum': ['turn_on', 'turn_off']
            },
            'bootmode': {
                'type': 'string'
            },
            'nextdevice': {
                'type': 'string'
            },
            'persistent': {
                'type': 'boolean'
            },
        },
        'required': [
            'operation'
        ]
    })
    def put(self, request, hostname):
        node = Node.objects.get(hostname=hostname)
        operation = request.data['operation']

        try:
            from ..utils.power import shutdown_device, startup_device
            if operation == 'turn_off':
                shutdown_device(node)
            else:
                startup_device(
                    node,
                    request.data.get('bootmode', 'uefi'),
                    request.data.get('nextdevice', None),
                    request.data.get('persistent', 'False')
                )

        except Exception as e:
            logger.exception(
                'Error occured when execute power operation'
            )
            raise PowerOperationException from e

        return Response()


class NodeInternalDetailView(InternalAPIView):

    def get(self, request, hostname):
        try:
            node = Node.objects.get(hostname=hostname)
        except Node.DoesNotExist:
            return Response({})
        else:
            return Response(node.as_dict())

    def delete(self, request, hostname):
        try:
            Node.objects.get(hostname=hostname).delete()
        except Node.DoesNotExist:
            return Response({})
        else:
            return Response({"hostname": hostname})


class NodeInternalAddView(InternalAPIView):
    @json_schema_validate({
        'type': 'object',
        'properties': {
            'hostname': {
                'type': 'string',
                'minLength': 1
            },
            'type': {
                'type': 'string',
                'enum': ["head", "login", "compute"]
            },
            "machinetype": {
                'type': 'string',
                'minLength': 1
            },
            'mgt_address': {
                'type': 'string',
                'minLength': 1
            },
            'bmc_address': {
                'type': 'string',
                'minLength': 1
            },
            'location_u': {
                "type": "integer",
                "minimum": 1
            },
            'rack': {
                'type': 'string',
                'minLength': 1
            },
            'chassis': {
                'type': 'string',
                'minLength': 1
            },
            'on_cloud': {
                'type': 'boolean'
            }
        },
        'required': ['hostname', 'type', 'machinetype', 'mgt_address', 'rack']
    })
    def post(self, request):
        hostname = request.data['hostname']
        kwargs = {
            "hostname": hostname,
            "type": request.data['type'],
            "machinetype": request.data['machinetype'],
            "mgt_address": request.data["mgt_address"],
            "bmc_address": request.data.get("bmc_address"),
            "location_u": request.data.get("location_u", 1),
            "on_cloud": request.data.get("on_cloud", True)
        }
        rack_name = request.data["rack"]
        try:
            rack = Rack.objects.get(name=rack_name)
        except Rack.DoesNotExist as e:
            raise Exception(
                f"can't find rack: {rack_name}"
            ) from e
        else:
            kwargs.update(rack=rack)
        chassis_name = request.data.get("chassis")
        if chassis_name:
            query_chassis = Chassis.objects.filter(
                name=chassis_name
            )
            if query_chassis:
                kwargs.update(chassis=query_chassis.first())
        try:
            node = Node.objects.create(**kwargs)
        except IntegrityError as e:
            raise Exception(
                f"The node hostname is {hostname} already exists"
            ) from e
        else:
            return Response(node.as_dict())
