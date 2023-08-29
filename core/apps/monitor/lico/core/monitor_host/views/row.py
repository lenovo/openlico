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

import json
import logging
from collections import defaultdict

from django.db.models import Sum
from rest_framework.response import Response

from lico.core.contrib.views import APIView
from lico.core.monitor_host.models import MonitorNode

from ..utils import ClusterClient

logger = logging.getLogger(__name__)


class RowView(APIView):
    def get(self, request):
        args = request.query_params.get('args', '{}')
        cluster_client = ClusterClient()
        row_racklist = cluster_client.get_row_racklist()

        vaild_rows = list()
        try:
            row = json.loads(args)["row"]
        except Exception:
            logger.warning("{}, param error.".format(args))
        else:
            for row_rack in row_racklist:
                if row_rack.name in row:
                    vaild_rows.append(row_rack)

        row_nodes = defaultdict(list)
        for row_rack in vaild_rows:
            for rack_node in cluster_client.get_rack_nodelist():
                if rack_node.name in row_rack.racks:
                    row_nodes[row_rack.name].extend(rack_node.hostlist)
        data = []
        for row, nodes_list in row_nodes.items():
            total = MonitorNode.objects.filter(
                hostname__in=nodes_list,
                power__isnull=False
            ).aggregate(
                total_energy=Sum("power")
            )
            total_energy = total.get('total_energy', None)
            data.append(
                {"name": row,
                 "total_energy": 0 if total_energy is None else total_energy}
            )
        return Response({
            "data": data
        })
