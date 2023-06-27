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

from lico.core.contrib.permissions import AsOperatorRole, AsUserRole

from .baseview import (
    ClusterTendencyBaseView, GroupHeatBaseView, GroupTendencyBaseView,
    NodeHistoryBaseView, NodeUtilHistoryView,
)


class NodeHistoryMemoryView(NodeHistoryBaseView):
    permission_classes = (AsOperatorRole,)

    def get_db_table(self):
        return 'node_metric'

    def get_db_metric(self):
        # return influxdb_metric, mariadb_metric
        return 'memory_util', 'memory_util'


class GroupTendencyMemoryView(GroupTendencyBaseView):
    permission_classes = (AsOperatorRole,)

    def get_db_table(self):  # pragma: no cover
        return 'nodegroup_metric'

    def get_db_metric(self):  # pragma: no cover
        return 'memory_util'


class GroupHeatMemoryView(GroupHeatBaseView):
    permission_classes = (AsOperatorRole,)

    def get_db_table(self):
        return "node_metric"

    def get_db_metric(self):
        return 'memory_util'


class ClusterTendencyMemoryView(ClusterTendencyBaseView):
    permission_classes = (AsOperatorRole,)

    def get_db_table(self):
        return 'nodegroup_metric'

    def get_db_metric(self):
        return 'memory_util'


class JobRunningNodeUtilHistoryView(NodeUtilHistoryView):
    permission_classes = (AsUserRole,)

    def get_db_table(self):
        return "node_metric", "job_monitor_metric"

    def get_db_metric(self):
        return "memory_util"
