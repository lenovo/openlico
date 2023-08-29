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

from lico.core.contrib.permissions import AsOperatorRole

from .baseview import (
    GroupHeatBaseView, GroupTendencyBaseView, NodeHistoryBaseView,
)


class NodeHistoryTemperatureView(NodeHistoryBaseView):
    permission_classes = (AsOperatorRole,)

    def get_db_table(self):
        return 'node_metric'

    def get_db_metric(self):
        # return influxdb_metric, mariadb_metric
        return 'node_temp', 'temperature'


class GroupTendencyTemperatureView(GroupTendencyBaseView):
    permission_classes = (AsOperatorRole,)

    TENDENCY_INTERVAL_TIME = {
        'hour': '60s',
        'day': '12m',
        'week': '1h24m',
        'month': '6h12m'
    }

    LAST_VALUE_PERIOD = '300s'

    def get_db_table(self):  # pragma: no cover
        return 'nodegroup_metric'

    def get_db_metric(self):  # pragma: no cover
        return 'temp'


class GroupHeatTemperatureView(GroupHeatBaseView):
    permission_classes = (AsOperatorRole,)

    LAST_VALUE_PERIOD = '300s'

    def get_db_table(self):
        return "node_metric"

    def get_db_metric(self):
        return 'node_temp'
