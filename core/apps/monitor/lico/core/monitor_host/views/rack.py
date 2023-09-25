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

from django.db.models import Sum
from rest_framework.response import Response

from lico.core.contrib.schema import json_schema_validate
from lico.core.contrib.views import APIView
from lico.core.monitor_host.models import MonitorNode
from lico.core.monitor_host.utils import (
    ClusterClient, get_node_statics, get_node_status_preference,
)

logger = logging.getLogger(__name__)


class RackView(APIView):

    @json_schema_validate({
        "type": "object",
        "properties": {
            "rack": {
                "type": "array",
                "items": {
                    "type": "string"
                }
            }
        },
        "required": ["rack"]
    })
    def post(self, request):
        preference = get_node_status_preference(request.user)

        try:
            rack = request.data["rack"]
        except Exception:
            logger.warning("{}, param error.".format(request.data))
            rack = []

        if len(rack) > 0:
            cluster_client = ClusterClient()
            rack_nodelist = cluster_client.get_rack_nodelist(rack)
        else:
            rack_nodelist = []
        data = list()
        for rack_node in rack_nodelist:
            hostlist = rack_node.hostlist
            if hostlist:
                power = MonitorNode.objects.filter(
                    hostname__in=hostlist,
                    power__isnull=False
                ).aggregate(
                    total=Sum('power')
                )
                node_statics = get_node_statics(
                    preference, rack_node.nodes)
                data.append({
                    "name": rack_node.name,
                    "energy": power['total'],
                    "node_busy": sum(node_statics["state"]["busy"]),
                    "node_free": sum(node_statics["state"]["idle"]),
                    "node_num": len(rack_node.hostlist),
                    "node_off": sum(node_statics["state"]["off"]),
                    "node_used": sum(node_statics["state"]["occupied"])
                })
            else:
                data.append({
                    "name": rack_node.name,
                    "energy": 0,
                    "node_busy": 0,
                    "node_free": 0,
                    "node_num": 0,
                    "node_off": 0,
                    "node_used": 0
                })

        return Response({
            "data": data
        })
