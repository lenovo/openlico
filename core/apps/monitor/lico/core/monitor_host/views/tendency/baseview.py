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
import re
from abc import ABCMeta, abstractmethod

from influxdb.exceptions import InfluxDBClientError, InfluxDBServerError
from rest_framework.response import Response

from lico.core.contrib.views import APIView
from lico.core.monitor_host.exceptions import InfluxDBException
from lico.core.monitor_host.models import Cluster, MonitorNode
from lico.core.monitor_host.utils import (
    ClusterClient, InfluxClient, align_data, convert_value, cut_list,
    get_new_time_rule, str_to_float,
)

CATEGORY_MAPPING = {
    'hour': '1h',
    'day': '1d',
    'week': '1w',
    'month': '31d'
}

logger = logging.getLogger(__name__)


class NodeHistoryBaseView(APIView, metaclass=ABCMeta):  # pragma: no cover
    TENDENCY_INTERVAL_TIME = {
        'hour': '30s',
        'day': '12m',
        'week': '1h24m',
        'month': '6h12m'
    }

    def get(self, request, hostname, category):
        node_obj = MonitorNode.objects.filter(hostname=hostname)
        if not node_obj.exists():
            return Response({})

        limit_time, span = get_new_time_rule(
            self.TENDENCY_INTERVAL_TIME[category],
            CATEGORY_MAPPING[category]
        )

        sql_history = self.get_history_sql().format(
            field_sql=self.get_scale_data['sql'],
            categ=category,
            table=self.get_db_table(),
            time=limit_time,
            interval=self.TENDENCY_INTERVAL_TIME[category]
        )
        logger.info("sql: %s", sql_history)
        influx_metric, mariadb_metric = self.get_db_metric()
        try:
            history = InfluxClient().get(
                sql_history,
                epoch='s',
                bind_params={"host": hostname,
                             "metric": influx_metric,
                             "metric_in": influx_metric + "_in",
                             "metric_out": influx_metric + "_out"}
            )
        except InfluxDBServerError or InfluxDBClientError as e:
            raise InfluxDBException from e
        history = self.handle_query_data(history)
        if history:
            history_last = history[-1].get("value")
            if history_last is None or history_last == "," \
                    or history_last == "None,None":
                history = cut_list(history, end=len(history) - 1,
                                   max_len=span, cut_from_start=False)
            else:
                history = cut_list(history, max_len=span, cut_from_start=False)
        current = self.get_current_data(node_obj, mariadb_metric)
        return self.return_success(history, current)

    @abstractmethod
    def get_db_table(self):
        pass

    @abstractmethod
    def get_db_metric(self):
        pass

    @property
    def get_scale_data(self):
        ''' sql: select [sql value] **
            handle_key: handle_query_data use handle_key'''
        return {'sql': 'last(value) as value', 'handle_key': ['value']}

    def get_history_sql(self):
        sql = "select {field_sql} from \"{categ}\".{table} where " \
              "host=$host and metric=$metric and time > now() - {time} " \
              "group by time({interval})"
        return sql

    def get_current_data(self, node_obj, mariadb_metric):
        node_list = node_obj.as_dict(
            include=[mariadb_metric, 'create_time']
        )
        if not node_list:
            return None, None
        value, time = node_list[0][mariadb_metric], node_list[0]['create_time']
        if value is None:
            return value, time
        return float(value), time

    def handle_query_data(self, data):
        data = map(convert_value, data.get_points())
        return list(data)

    def return_success(self, history, current):
        current_value, current_time = current
        return_data = {
            "history": history if history else [],
            'current': str(current_value),
            "current_time": current_time
        }
        return Response(return_data)


class GroupTendencyBaseView(APIView, metaclass=ABCMeta):  # pragma: no cover
    TENDENCY_INTERVAL_TIME = {
        'hour': '30s',
        'day': '12m',
        'week': '1h24m',
        'month': '6h12m'
    }

    def get(self, request, groupname, category):
        limit_time, span = get_new_time_rule(
            self.TENDENCY_INTERVAL_TIME[category],
            CATEGORY_MAPPING[category]
        )

        sql_history = self.get_history_sql().format(
            field_sql=self.get_scale_data['sql'],
            categ=category,
            table=self.get_db_table(),
            categ_m=limit_time,
            time=self.TENDENCY_INTERVAL_TIME[category]
        )

        logger.info("sql: %s", sql_history)
        metric = self.get_db_metric()
        try:
            history = InfluxClient().get(
                sql_history,
                epoch='s',
                bind_params={
                    "host": groupname,
                    "metric": metric,
                    "metric_in": metric + "_in",
                    "metric_out": metric + "_out"
                }
            )
        except InfluxDBClientError or InfluxDBServerError as e:
            raise InfluxDBException from e
        history = self.handle_query_data(history)
        if history:
            history_last = history[-1].get("value")
            if history_last is None or history_last == "," \
                    or history_last == "None,None":
                history = cut_list(history, end=len(history) - 1,
                                   max_len=span, cut_from_start=False)
            else:
                history = cut_list(history, max_len=span, cut_from_start=False)

        sql_current = self.get_current_sql().format(
            categ=category,
            table=self.get_db_table()
        )
        logger.info("sql: %s", sql_current)
        current = self.get_current_data(sql_current, groupname)
        return self.return_success(history, current)

    @abstractmethod
    def get_db_table(self):
        pass

    @abstractmethod
    def get_db_metric(self):
        pass

    @property
    def get_scale_data(self):
        ''' sql: select [sql value] **
            handle_key: handle_query_data use handle_key'''
        return {'sql': 'last(value) as value', 'handle_key': ['value']}

    def get_history_sql(self):
        sql = "select {field_sql} from \"{categ}\".{table} \
        where host=$host and metric=$metric and time > now() - {categ_m} \
        group by time({time})"
        return sql

    def get_current_sql(self):
        sql = "select last(value) from \"{categ}\".{table} where " \
              "host=$host and metric=$metric"
        return sql

    def get_current_data(self, sql, groupname):
        ret = InfluxClient().get(sql,
                                 epoch='s',
                                 bind_params={"host": groupname,
                                              "metric": self.get_db_metric()})
        current_value = current_time = None
        for p in ret.get_points():
            current_value = p.get('last')
            current_time = p.get('time')
        return current_value, current_time

    def handle_query_data(self, data, *args, **kwargs):
        return list(data.get_points())

    def return_success(self, history, current):
        current_value, current_time = current
        return_data = {"history": history if history else [],
                       # last value may be None
                       'current': current_value,
                       'current_time': current_time}
        return Response(return_data)


class GroupHeatBaseView(APIView, metaclass=ABCMeta):  # pragma: no cover
    LAST_VALUE_PERIOD = '30s'

    def get(self, request, groupname):
        nodesdata = ClusterClient().get_group_nodelist(groupname)
        # nodesdata = list(groupobject.nodes.values("id", "hostname"))
        metric = self.get_db_metric()
        if len(metric) == 2:
            _params = {}
            for _metric in metric:
                _params.update({f"{_metric}_in": f"{_metric}_in",
                                f"{_metric}_out": f"{_metric}_out"})
        else:
            _params = {"metric": metric}
        try:
            for item in nodesdata:
                sql = self.get_sql().format(
                    field_sql=self.get_scale_data['sql'],
                    table=self.get_db_table(),
                    period=self.LAST_VALUE_PERIOD
                )
                logger.info("sql:%s", sql)
                data = InfluxClient().get(sql,
                                          bind_params=dict({
                                              "host": item['hostname']
                                          }, **_params))
                data = self.handle_query_data(data)
                item.update(data)
        except InfluxDBServerError or InfluxDBClientError as e:
            raise InfluxDBException from e
        return self.return_success(nodesdata)

    @abstractmethod
    def get_db_table(self):
        pass

    @abstractmethod
    def get_db_metric(self):
        pass

    @property
    def get_scale_data(self):
        ''' sql: select [sql value] **
            handle_key: handle_query_data use handle_key'''
        return {'sql': 'LAST(value)', 'handle_key': ['last']}

    def get_sql(self):
        sql = "select {field_sql} from hour.{table} where  host=$host \
         and metric=$metric and time > now() - {period}"
        return sql

    def handle_query_data(self, data):
        handle_key = self.get_scale_data['handle_key'][0]
        for item in data.get_points():
            return {'value': str_to_float(item[handle_key])}
        else:
            return {'value': None}

    def return_success(self, data, *args, **kwargs):
        return Response({"heat": data})


class GroupHeatGpuBaseView(GroupHeatBaseView):  # pragma: no cover

    def get_sql(self):
        sql = "select {field_sql} from hour.{table} where  host=$host \
         and metric=$metric and index=$index and time > now() - {period}"
        return sql

    def get(self, request, groupname):
        gpu_heat_data = []
        nodesdata = ClusterClient().get_group_nodelist(groupname)
        # nodesdata = list(groupobject.nodes.values("id", "hostname"))
        metric = self.get_db_metric()
        _params = {"metric": metric}
        try:
            for item in nodesdata:
                hostname = item['hostname']
                gpu_number = MonitorNode.objects.get(
                    hostname=hostname).gpu.count()
                for index in range(gpu_number):
                    _params['index'] = str(index)
                    sql = self.get_sql().format(
                        field_sql=self.get_scale_data['sql'],
                        table=self.get_db_table(),
                        period=self.LAST_VALUE_PERIOD
                    )
                    logger.info("sql:%s", sql)
                    data = InfluxClient().get(sql,
                                              bind_params=dict({
                                                  "host": hostname
                                              }, **_params))
                    data = self.handle_query_data(data)
                    gpu_heat_data.append({"hostname": hostname,
                                          "gpu_index": index,
                                          "value": data['value']})
        except InfluxDBServerError or InfluxDBClientError as e:
            raise InfluxDBException from e
        return self.return_success(gpu_heat_data)


class ClusterTendencyBaseView(APIView, metaclass=ABCMeta):  # pragma: no cover
    TENDENCY_INTERVAL_TIME = {
        'hour': '30s',
        'day': '12m',
        'week': '1h24m',
        'month': '6h12m'
    }

    def get(self, request, category):
        limit_time, span = get_new_time_rule(
            self.TENDENCY_INTERVAL_TIME[category],
            CATEGORY_MAPPING[category]
        )

        sql_history = self.get_history_sql().format(
            field_sql=self.get_scale_data['sql'],
            categ=category,
            table=self.get_db_table(),
            time=limit_time,
            interval=self.TENDENCY_INTERVAL_TIME[category]
        )
        logger.info("sql: %s", sql_history)
        try:
            history = InfluxClient().get(
                sql_history,
                epoch='s',
                bind_params={
                    "host": 'all',
                    "metric": self.get_db_metric()
                }
            )
        except InfluxDBClientError or InfluxDBServerError as e:
            raise InfluxDBException from e
        history = self.handle_query_data(history)
        if history and history[-1].get("value") is None:
            history = cut_list(history, end=len(history) - 1, max_len=span,
                               cut_from_start=False)
        current = self.get_current_data()
        return self.return_success(history, current)

    @abstractmethod
    def get_db_table(self):
        pass

    @abstractmethod
    def get_db_metric(self):
        pass

    @property
    def get_scale_data(self):
        ''' sql: select [sql value] **
            handle_key: handle_query_data use handle_key'''
        return {'sql': 'last(value) as value', 'handle_key': ['value']}

    def get_history_sql(self):
        sql = "select {field_sql} from \"{categ}\".{table} \
        where host=$host and metric=$metric \
        and time > now() - {time} group by time({interval})"
        return sql

    def get_current_data(self):
        metric = self.get_db_metric()
        current_value = current_time = None
        metric_mapping = {
            'memory_util': ['memory_used', 'memory_total'],
            'disk_util': ['disk_used', 'disk_total'],
            'gpu_mem_usage': ['gpu_memory_used', 'gpu_memory_total']
        }
        if metric not in metric_mapping:
            cluster_data = Cluster.objects.filter(metric=metric)
            if cluster_data is None:
                return current_value, current_time
            data_dict = cluster_data.first().as_dict(
                include=['value', 'create_time']
            )
            return float(data_dict['value']), data_dict['create_time']

        usage_obj_list = Cluster.objects.filter(
            metric__in=metric_mapping[metric]
        ).as_dict(include=['metric', 'value', 'create_time'])
        total = used = None
        usage_re = re.compile('^.*(total)$')
        for usage_dict in usage_obj_list:
            if usage_re.match(usage_dict['metric']):
                total = float(usage_dict['value'])
                continue
            used = float(usage_dict['value'])
            current_time = usage_dict['create_time']

        if total is None or used is None or total <= 0 or used < 0:
            return current_value, current_time
        return round(100.0 * used/total, 2), current_time

    def handle_query_data(self, data, *args, **kwargs):
        return list(data.get_points())

    def return_success(self, history, current):
        current_value, current_time = current
        return_data = {"history": history if history else [],
                       # last value may be None
                       'current': float(current_value),
                       'current_time': current_time}
        return Response(return_data)


class NodeUtilHistoryView(APIView, metaclass=ABCMeta):
    node_metric = dict()

    TENDENCY_INTERVAL_TIME = {
        'hour': '30s',
        'day': '12m',
        'week': '1h24m',
        'month': '6h12m'
    }

    def get(self, request, hostname, category):
        node = MonitorNode.objects.filter(hostname=hostname)
        if not node.exists():
            logger.exception("%s is not exist" % hostname)
            return Response({})
        self.node_metric.update(
            node[0].as_dict(include=['memory_total', 'cpu_total'])
        )
        if self.node_metric['memory_total'] == 0 or \
                self.node_metric['cpu_total'] == 0:
            logger.exception(
                "%s: memory total or cpu total is zero" % hostname)
            return Response({})
        scheduler_id = request.query_params.get("scheduler_id", None)
        sql_history = self.get_history_sql().format(
            category=category,
            sys_table=self.get_db_table()[0],
            job_table=self.get_db_table()[1],
            category_time=CATEGORY_MAPPING[category],
            interval=self.TENDENCY_INTERVAL_TIME[category]
        )
        logger.info("sql: %s", sql_history)
        try:
            history = InfluxClient().get(
                sql_history,
                epoch='s',
                bind_params={
                    "host": hostname,
                    "sys_metric": self.get_db_metric(),
                    "job_metric": 'mem_used'
                    if self.get_db_metric() == 'memory_util'
                    else self.get_db_metric(),
                    "scheduler_id": scheduler_id
                }
            )
        except InfluxDBServerError or InfluxDBClientError as e:
            raise InfluxDBException from e
        history = self.convert_query_data(self.handle_query_data(history))
        sql_current = self.get_current_sql().format(
            category=category,
            sys_table=self.get_db_table()[0],
            job_table=self.get_db_table()[1]
        )
        logger.info("sql: %s", sql_current)
        current = self.get_current_data(sql_current, hostname, scheduler_id)
        return self.return_success(history, current)

    @abstractmethod
    def get_db_table(self):
        pass

    @abstractmethod
    def get_db_metric(self):
        pass

    @staticmethod
    def handle_query_data(result_set_lists):
        return align_data(result_set_lists)

    def get_history_sql(self):
        node_sql = """
        select last(value) as system_util from {category}.{sys_table} \
        where \
        host=$host and \
        metric=$sys_metric and \
        time > now() - {category_time} \
        group by time({interval});
        """
        job_sql = """
        select last(value) as job_util from {category}.{job_table} \
        where \
        host=$host and \
        metric=$job_metric and \
        scheduler_id=$scheduler_id and \
        time > now() - {category_time} \
        group by time({interval});
        """
        return node_sql + job_sql

    def convert_query_data(self, datas):
        if not datas:
            return []
        node_data, job_data = datas
        for data in node_data:
            data['system_util'] = str_to_float(data['system_util'])
        for data in job_data:
            if data['job_util'] is None:
                continue
            util = str_to_float(data['job_util'])
            if self.get_db_metric() == 'cpu_util':
                data['job_util'] = \
                    round(util / self.node_metric['cpu_total'], 1)
            elif self.get_db_metric() == 'memory_util':
                data['job_util'] = \
                    round(100 * util / self.node_metric['memory_total'], 1)
        for i in range(len(node_data)):
            node_data[i].update(job_data[i])
        return node_data

    def get_current_sql(self):
        node_sql = """
        select last(value) as system_util from {category}.{sys_table} \
        where \
        host=$host and \
        metric=$sys_metric;
        """
        job_sql = """
        select last(value) as job_util from {category}.{job_table} \
        where \
        host=$host and \
        metric=$job_metric and \
        scheduler_id=$scheduler_id;
        """
        return node_sql + job_sql

    def get_current_data(self, sql_current, hostname, scheduler_id):
        node_curr_data, job_curr_data = \
            InfluxClient().get(
                sql_current,
                epoch='s',
                bind_params={
                    "host": hostname,
                    "sys_metric": self.get_db_metric(),
                    "job_metric": 'mem_used'
                    if self.get_db_metric() == 'memory_util'
                    else self.get_db_metric(),
                    "scheduler_id": scheduler_id
                })
        node_current = list(node_curr_data.get_points())
        job_current = list(job_curr_data.get_points())
        current = dict()
        current_time = None
        if not node_current:
            return current, current_time
        current['system_util'] = \
            str_to_float(node_current[0].get('system_util'))
        if not job_current:
            return current, current_time
        job_util = str_to_float(job_current[0].get('job_util'))
        if job_util is None:
            current['job_util'] = job_util
        elif self.get_db_metric() == 'cpu_util':
            current['job_util'] = \
                round(job_util / self.node_metric['cpu_total'], 1)
        elif self.get_db_metric() == 'memory_util':
            current['job_util'] = \
                round(100.0 * job_util / self.node_metric['memory_total'], 1)
        current_time = job_current[0]['time'] \
            if job_current[0]['time'] >= node_current[0]['time'] \
            else node_current[0]['time']

        return current, current_time

    def return_success(self, history, current):
        current_value, current_time = current
        history = list(history) if history else []
        if history and history[-1].get("job_util") is None:
            history.pop()

        return_data = {
            "history": history,
            'current': current_value,
            "current_time": current_time
        }
        return Response(return_data)
