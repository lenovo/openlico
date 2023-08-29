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
import logging

from lico.core.contrib.permissions import AsOperatorRole
from lico.core.monitor_host.utils import InfluxClient

from .baseview import (
    GroupHeatBaseView, GroupTendencyBaseView, NodeHistoryBaseView,
)

logger = logging.getLogger(__name__)


class NodeHistoryNetworkView(NodeHistoryBaseView):
    permission_classes = (AsOperatorRole,)

    def get_db_table(self):
        return 'node_metric'

    def get_db_metric(self):
        # return influxdb_metric, mariadb_metric
        return 'eth', 'eth'

    @property
    def get_scale_data(self):
        return {'sql': 'last(value) as value', 'handle_key': ['value']}

    def get_history_sql(self):
        sql_in = "select {field_sql} from \"{categ}\".{table} where \
         host=$host and metric=$metric_in"
        sql_out = "select {field_sql} from \"{categ}\".{table} where \
         host=$host and metric=$metric_out"
        time_query = "and time > now() - {time} group by time({interval})"
        sql = "%s %s;%s %s" % (sql_in, time_query, sql_out, time_query)
        return sql

    def get_current_data(self, node_obj, mariadb_metric):
        metric_in = mariadb_metric+'_in'
        metric_out = mariadb_metric+'_out'
        metric_list = node_obj.as_dict(
            include=[metric_in, metric_out, 'create_time']
        )
        if not metric_list:
            return ',', None

        net_in, net_out = metric_list[0][metric_in], metric_list[0][metric_out]
        network_in = '' if net_in is None else net_in
        network_out = '' if net_out is None else net_out
        time = metric_list[0]['create_time']
        return ','.join([str(network_in), str(network_out)]), time

    def handle_query_data(self, data):
        ret = []
        ret_in = list(data[0].get_points())
        ret_out = list(data[1].get_points())

        handle_key = self.get_scale_data['handle_key'][0]

        for index, itemd in enumerate(ret_in):
            try:
                value = "{0},{1}".format(
                    itemd[handle_key],
                    ret_out[index][handle_key],
                )
            except Exception:
                value = ","
            ret.append({'time': itemd['time'], 'value': value})

        return ret


class GroupTendencyNetworkView(GroupTendencyBaseView):
    permission_classes = (AsOperatorRole,)

    def get_db_table(self):  # pragma: no cover
        return 'nodegroup_metric'

    def get_db_metric(self):  # pragma: no cover
        # return influxdb_metric
        return 'eth'

    @property
    def get_scale_data(self):  # pragma: no cover
        return {'sql': 'last(value) as value', 'handle_key': ['value']}

    def get_history_sql(self):  # pragma: no cover
        sql_in = "select {field_sql} from \"{categ}\".{table} where \
        host=$host and metric=$metric_in"
        sql_out = "select {field_sql} from \"{categ}\".{table} where \
        host=$host and metric=$metric_out"

        time_query = "and time > now() - {categ_m} group by time({time})"
        sql = "%s %s;%s %s" % (sql_in, time_query, sql_out, time_query)
        return sql

    def get_current_sql(self):  # pragma: no cover
        sql_in = "select last(value) from \"{categ}\".{table} where " \
                 "host=$host and metric=$metric_in"

        sql_out = "select last(value) from \"{categ}\".{table} where " \
                  "host=$host and metric=$metric_out"
        return sql_in + ';' + sql_out

    def get_current_data(self, sql, groupname):  # pragma: no cover
        metric = self.get_db_metric()
        ret = InfluxClient().get(sql,
                                 epoch='s',
                                 bind_params={
                                     "host": groupname,
                                     "metric_in": metric + "_in",
                                     "metric_out": metric + "_out"
                                 })
        current = [str(p.get('last', ''))
                   for a in ret for p in a.get_points()]
        current_time = [t.get('time') for t in ret[0].get_points()]

        return (
            ','.join(current) if len(current) == 2 else ',',
            current_time[0] if current_time else None
        )

    def handle_query_data(self, data, *args, **kwargs):  # pragma: no cover
        ret = []
        ret_in = list(data[0].get_points())
        ret_out = list(data[1].get_points())

        handle_key = self.get_scale_data['handle_key'][0]

        for index, itemd in enumerate(ret_in):
            try:
                value = "{0},{1}".format(
                    itemd[handle_key],
                    ret_out[index][handle_key],
                )
            except Exception:
                value = ","
            ret.append({'time': itemd['time'], 'value': value})

        return ret


class GroupHeatNetworkView(GroupHeatBaseView):
    permission_classes = (AsOperatorRole,)

    def get_db_table(self):
        return 'node_metric'

    def get_db_metric(self):
        return 'eth', 'ib'

    @property
    def get_scale_data(self):
        return {'sql': 'last(value)', 'handle_key': ['last']}

    def sql_factory(self, db_metric):
        db_in = f"{db_metric}_in"
        db_out = f"{db_metric}_out"
        sql_in = "select {field_sql} from hour.{table} where " \
                 "host=$host and metric=$%s " \
                 "and time > now() - {period}"
        sql_out = "select {field_sql} from hour.{table} where " \
                  "host=$host and metric=$%s " \
                  "and time > now() - {period}"
        sql = "%s;%s" % (sql_in % db_in, sql_out % db_out)
        return sql

    def get_sql(self):
        eth, ib = self.get_db_metric()
        eth_sql = self.sql_factory(eth)
        ib_sql = self.sql_factory(ib)
        return f"{eth_sql};{ib_sql}"

    def handle_query_data(self, data):
        handle_key = self.get_scale_data['handle_key'][0]
        value = []
        for ret in (data[:2], data[2:]):
            current = [p.get(handle_key, '')
                       for a in ret
                       for p in a.get_points()]
            value += current if len(current) == 2 else ['', '']

        return {'value': ','.join(value)}


class NodeHistoryIbView(NodeHistoryNetworkView):
    def get_db_metric(self):
        return 'ib', 'ib'


class GroupTendencyIbView(GroupTendencyNetworkView):
    def get_db_metric(self):  # pragma: no cover
        return 'ib'
