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

from django.conf import settings

from lico.core.contrib.client import Client

from ..utils import (
    get_hosts_from_job, get_hosts_from_running_job, get_resource_from_job,
    sum_resource,
)

logger = logging.getLogger(__name__)


class QueryRes(object):
    """
    query resource data by query_params, from client api

    client api:
        get cluster data: monitor_client().get_cluster_resource
            return_value: instance of ResData, attr: hostname, status, data
                return_value: instance of ResData,
                attr:
                    str hostname,
                    str status,
                    dict data:
                        key: one of ['cpu', 'mem', Gres]
                        value: instance of ResUtil,
                            attr:
                                float total,
                                float usage,
                                enum total_unit, value: 0 -> FIXED
                                enum usage_unit, value: 0 or 1 -> PERCENTAGE
                                int index
        get scheduler data - monitor_client().get_scheduler_res_listource
            return_value: same as `cluster data`
        get running_job data - job_client().query_running_jobs
            return_value: instance of Job,
                attr:
                    int id,
                    str scheduler_id,
                    str submitter,
                    list job_running,
                    other(unused)...

    """

    def __init__(self, filter_type, filter_value, is_dict=False):
        self.filter_type = filter_type
        self.filter_value = filter_value
        self.is_dict = is_dict
        self.cc = Client().cluster_client()
        self.mc = Client().monitor_client()
        self.jc = Client().job_client()

    @staticmethod
    def allocated_resource(job_data):
        """
        :return: dict
           example: {
               'node-c1': {
                   'cpu': 36.0, 'mem': 888888, 'gpu': 2.0
               },
               'node-c2': {
                   'cpu': 48.0, 'mem': 666666, 'gpu': 1.0, 'fpga': 0.0
                },
           }
        """
        allocated_dict = dict()
        for job_obj in job_data:
            resource = get_resource_from_job(job_obj)
            for host in get_hosts_from_job(job_obj):
                hostname = host.lower()
                if hostname in allocated_dict:
                    sum_resource(
                        allocated_dict[hostname], resource[hostname])
                else:
                    allocated_dict[hostname] = resource[hostname]

        return allocated_dict

    def filter_hostname(self, filter_type, filter_value, job_data):
        """
        Get hosts name from cluster or running jobs.
        :return: list hostname_list
            enum: str
        """
        hostname_list = []
        if filter_type == 'all':
            hostname_list = [node.hostname for node in self.cc.get_nodelist()]

        elif filter_type == 'group':
            for group in self.cc.get_group_nodelist():
                if group.name == filter_value:
                    hostname_list = group.hostlist

        elif filter_type == 'rack':
            for rack in self.cc.get_rack_nodelist():
                if rack.name == filter_value:
                    hostname_list = rack.hostlist

        elif filter_type == 'job':
            hostname_list = get_hosts_from_running_job(
                'scheduler_id', job_data, filter_value)

        elif filter_type == 'submitter':
            hostname_list = get_hosts_from_running_job(
                'submitter', job_data, filter_value)

        return hostname_list

    @property
    def data_to_portal(self):
        data = []
        os_data = self.mc.get_cluster_resource()
        scheduler_data = self.mc.get_scheduler_resource()
        job_data = self.jc.query_running_jobs()
        hostname_list_lower = [
            host.lower() for host in self.filter_hostname(
                self.filter_type, self.filter_value, job_data)]
        allocated_resource = self.allocated_resource(job_data)
        host_res_dict = dict()
        for scheduler_res_data_obj in scheduler_data:
            hostname = scheduler_res_data_obj.hostname.lower()
            host_res_dict[hostname] = scheduler_res_data_obj
        for os_res_data_obj in os_data:
            hostname = os_res_data_obj.hostname.lower()
            if hostname in hostname_list_lower and (
                    os_res_data_obj.status == 'on'):
                result = self.analyse_res_data_obj(
                    os_res_data_obj,
                    host_res_dict.get(hostname, None),
                    allocated_resource.get(hostname, {})
                )
                if self.is_dict:
                    result = self.analyse_res_data_obj_dict(
                        os_res_data_obj,
                        host_res_dict.get(hostname, None),
                        allocated_resource.get(hostname, {})
                    )
                data.append(result)

        return data

    @staticmethod
    def analyse_res_data_obj(os_obj, scheduler_obj, resource_allocated):
        """
        os_obj: instance of ResData,
            attr:
                hostname: str, name of host
                status: str, status of host or scheduler
                data: default_dict,
                    key: str, resource name
                    value: instance of ResUtilization, resource info
        scheduler_obj: instance of ResData, same of os_obj
        resource_allocated: dict,
            key: str, resource name,
            value: float, resource usage

        :return: dict,
            example - {
                'hostname': 'c1',
                'cpu': [36.0, 15.0, 6.0, 0.0, 6.0],
                'mem': [100000.0, 12.0, 0, 0.0, 10000.0],
                'gpu': [1.0, 0.0, 0.0, 0.0, 0.0],
                'gpu_mem': [16670720.0, 0, 0.0, 0.0, 16670720.0]}
        """
        res_obj_to_res_dict = dict()
        res_obj_to_res_dict['hostname'] = os_obj.hostname
        gpu_mig_code = f'{settings.MAINTENANCE.get("Gpu")}_mig_mode'
        for key, value_list in os_obj.data.items():
            if gpu_mig_code == key:
                continue
            allocated = resource_allocated.get(key, 0.0)
            if scheduler_obj is not None:
                if key in scheduler_obj.data:
                    res_obj_to_res_dict[key] = HostResSummary(
                        os_obj.data[key], scheduler_obj.data[key], allocated
                    ).to_list()
                    res_obj_to_res_dict[key] = \
                        HostResSummary.calculate_gpu_num_with_mig(
                            key,
                            res_obj_to_res_dict[key],
                            os_obj.data.get(gpu_mig_code, [])
                        )
                    continue
            res_obj_to_res_dict[key] = HostResSummary(
                os_obj.data[key], None, allocated
            ).to_list()
            res_obj_to_res_dict[key] = \
                HostResSummary.calculate_gpu_num_with_mig(
                    key,
                    res_obj_to_res_dict[key],
                    os_obj.data.get(gpu_mig_code, [])
                )

            logger.error(
                'Scheduler resource empty, check it out! '
                'hostname: %s, resource name: %s',
                res_obj_to_res_dict['hostname'], key)

        return res_obj_to_res_dict

    @staticmethod
    def analyse_res_data_obj_dict(os_obj, scheduler_obj, resource_allocated):
        """
        The differences between the function `analyse_res_data_obj` is
        that it returns a dict instead of a list on every resource, and it
        carries the number of schedulable resource instead of unschedulable
        one.

        MIG mode, hypervisor vendor and sockets are ignored in this function.

        os_obj: instance of ResData,
            attr:
                hostname: str, name of host
                status: str, status of host or scheduler
                data: default_dict,
                    key: str, resource name
                    value: instance of ResUtilization, resource info
        scheduler_obj: instance of ResData, same of os_obj
        resource_allocated: dict,
            key: str, resource name,
            value: float, resource usage

        :return: dict,
            example - {
                'hostname': 'c1',
                'cpu': {
                    "total": 36.0,
                    "schedulable": 30.0,
                    "allocated": 6.0,
                    "job_used": 15.0,
                    "system_used": 0.0
                },
                'memory': {
                    "total": 395659548,
                    "scheduable": 300000000,
                    "allocated": 200000,
                    "job_used": 90.23,
                    "system_used": 2.012
                },
                ......}
        """
        res_obj_to_res_dict = dict()
        res_obj_to_res_dict['hostname'] = os_obj.hostname
        gpu_mig_code = f'{settings.MAINTENANCE.get("Gpu")}_mig_mode'
        for key, value_list in os_obj.data.items():
            if key in [gpu_mig_code, "hypervisor_vendor", "sockets"]:
                continue

            res_key = key
            if "mem" in res_key:
                res_key = res_key.replace("mem", "memory")

            allocated = resource_allocated.get(key, 0.0)
            if scheduler_obj is not None:
                if key in scheduler_obj.data:
                    res_obj_to_res_dict[res_key] = HostResSummary(
                        os_obj.data[key], scheduler_obj.data[key], allocated
                    ).to_dict()
                    res_obj_to_res_dict[res_key] = \
                        HostResSummary.calculate_gpu_related_with_mig_dict(
                            key,
                            res_obj_to_res_dict[res_key],
                            os_obj.data.get(gpu_mig_code, [])
                        )
                    continue
            res_obj_to_res_dict[res_key] = HostResSummary(
                os_obj.data[key], None, allocated
            ).to_dict()
            res_obj_to_res_dict[res_key] = \
                HostResSummary.calculate_gpu_related_with_mig_dict(
                    key,
                    res_obj_to_res_dict[res_key],
                    os_obj.data.get(gpu_mig_code, [])
                )

            logger.error(
                'Scheduler resource empty, check it out! '
                'hostname: %s, resource name: %s',
                res_obj_to_res_dict['hostname'], key)

        return res_obj_to_res_dict


class HostResSummary(object):
    def __init__(self, os_res_list, scheduler_res_list, allocated):
        self.os_total = self.calculate_total(os_res_list)
        self.scheduler_total = self.calculate_total(scheduler_res_list)
        self.os_util = self.calculate_util(os_res_list)
        self.scheduler_util = self.calculate_util(scheduler_res_list)
        self.allocated = allocated
        self.os_res_list = os_res_list
        self.scheduler_res_list = scheduler_res_list

    @staticmethod
    def calculate_total(res_list):
        if res_list is None:
            return None
        total = 0.0
        for res_obj in res_list:
            if res_obj.total < 0:
                return None
            else:
                total += res_obj.total
        return total

    @staticmethod
    def calculate_gpu_num_with_mig(key, res, mig_info):
        """
        res: [total, job_used, allocated, system_used, non_schedulable]
        """
        import copy
        ret = copy.deepcopy(res)
        if key == settings.MAINTENANCE.get("Gpu"):
            use_mig_gpu_num = 0
            mig_total = 0
            for gpu in mig_info:
                if gpu.usage:
                    use_mig_gpu_num += 1
                    mig_total += gpu.total
            if res[0]:
                ret[0] = res[0] - use_mig_gpu_num + mig_total
            if res[1] and res[2]:
                ret[1] = res[2] * 100 / ret[0]
            if res[-1]:
                ret[-1] = res[-1] - use_mig_gpu_num + mig_total
        return ret

    @staticmethod
    def calculate_gpu_related_with_mig_dict(key, res, mig_info):
        """
        res: {
            "total": xxx,
            "job_used": xxx,
            "allocated": xxx,
            "system_used": xxx,
            "schedulable": xxx
        }
        """
        import copy
        ret = copy.deepcopy(res)
        if key == settings.MAINTENANCE.get("Gpu"):
            use_mig_gpu_num = 0
            mig_total = 0
            for gpu in mig_info:
                if gpu.usage:
                    use_mig_gpu_num += 1
                    mig_total += gpu.total
            if res["total"]:
                ret["total"] = res["total"] - use_mig_gpu_num + mig_total
            if res["job_used"] and res["allocated"]:
                ret["job_used"] = res["allocated"] * 100 / ret["total"]

        if key == "gpu_mem":
            ret["job_used"] = None
            ret["allocated"] = None
            ret["system_used"] = None

        return ret

    @staticmethod
    def calculate_util(res_list):
        if res_list is None:
            return None
        util = 0.0
        for res_obj in res_list:
            if res_obj.usage < 0:
                return None
            if res_obj.usage_unit.value == 0:
                # FIXED
                util += res_obj.usage
            else:
                # res_obj.usage_unit.value == 1: PERCENTAGE
                util += res_obj.usage * res_obj.total / 100
        return util

    def reset_util(self, os_util, scheduler_util):
        if os_util is not None and scheduler_util is not None:
            if len(self.os_res_list) == 1 and self.os_res_list[0].index < 0:
                # CPU or MEM
                os_util = max(os_util, scheduler_util)
            else:
                # Gres
                os_util = max(os_util, scheduler_util)
                scheduler_util = max(os_util, scheduler_util)
        return os_util, scheduler_util

    @property
    def job_used(self):
        if self.scheduler_util is not None:
            os_util, scheduler_util = self.reset_util(
                self.os_util, self.scheduler_util)
            return scheduler_util * 100 / self.os_total
        elif self.allocated == 0 and self.scheduler_util is None and (
                self.os_util is not None
        ):
            return 0
        else:
            return None

    @property
    def non_schedulable(self):
        if self.scheduler_util is not None and self.os_util is not None:
            return self.os_total - self.scheduler_total
        elif self.scheduler_util is None and self.allocated == 0 and (
                self.os_total is not None
        ):
            return self.os_total
        else:
            return None

    @property
    def system_used(self):
        if self.os_util is not None and self.scheduler_util is not None:
            os_util, scheduler_util = self.reset_util(
                self.os_util, self.scheduler_util)
            return (os_util - scheduler_util) * 100 / self.os_total
        elif (self.allocated == 0) and (self.scheduler_util is None) and (
                self.os_util is not None) and self.os_total != 0:
            return self.os_util * 100 / self.os_total
        else:
            return None

    def to_list(self):
        if self.system_used is None:
            return [None for _ in range(5)]
        return [self.os_total, self.job_used, self.allocated,
                self.system_used, self.non_schedulable]

    def to_dict(self):
        res = {
            "total": self.os_total,
            "schedulable": self.scheduler_total,
            "allocated": self.allocated if self.scheduler_total else None,
            "job_used": self.job_used if self.scheduler_total else None,
            "system_used": self.system_used
        }
        return res
