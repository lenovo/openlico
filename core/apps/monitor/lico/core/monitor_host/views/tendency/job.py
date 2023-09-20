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

from rest_framework.response import Response

from lico.core.contrib.permissions import AsOperatorRole
from lico.core.contrib.views import APIView
from lico.core.monitor_host.utils import ClusterClient, get_allocation_core

from .baseview import GroupTendencyBaseView


class GroupTendencyJob(GroupTendencyBaseView):
    permission_classes = (AsOperatorRole,)

    def get_db_table(self):  # pragma: no cover
        return 'nodegroup_metric'

    def get_db_metric(self):  # pragma: no cover
        return 'allocating_core'


class GroupHeatJob(APIView):
    permission_classes = (AsOperatorRole,)

    def get(self, request, groupname):
        data = list()
        group_nodes = list()
        for group in ClusterClient().get_nodegroup_nodelist():
            if group.name == groupname:
                group_nodes.extend([node.hostname for node in group.nodes])
                break
        if not group_nodes:
            return Response({'heat': data})
        """
        ResultSet for example:
        {
            'head': 10,
            'c1': 0
        }
        """
        nodes_alloc = get_allocation_core()
        for node in group_nodes:
            data.append({'hostname': node, 'value': nodes_alloc.get(node, 0)})
        return Response({'heat': data})
