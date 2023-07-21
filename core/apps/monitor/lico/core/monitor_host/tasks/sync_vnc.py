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
import re
from ast import literal_eval

import attr

from lico.core.monitor_host.models import MonitorNode
from lico.core.monitor_host.utils import NodeSchedulerProcess, init_datasource
from lico.ssh.ssh_connect import RemoteSSH

logger = logging.getLogger(__name__)


def sync_vnc():
    monitor_data = init_datasource()
    for nodes_info in monitor_data:
        try:
            node_dict = attr.asdict(nodes_info.node_metric)
            save_vnc_into_mariadb(nodes_info.hostname, node_dict)
        except Exception as e:
            logger.error(e)


def save_vnc_into_mariadb(hostname, node_metric):
    vnc_dict = parse_vnc(node_metric)
    node, _ = MonitorNode.objects.get_or_create(hostname=hostname)

    # compare the vnc data from icinga and mariadb, if icinga gets a new vnc,
    # the code will call get_scheduler_id_pid function to get the mapping of
    # pid,job_id,scheduler_id and update it into mariadb
    repull_flag = cmp_vnc_details(vnc_dict, node.vnc.as_dict())

    if repull_flag:

        # if repull_flag=true, call the function(get_scheduler_id_pid); if
        # false, it means there is no new vnc data.
        # if error occurs and pid_scheduler is empty, don't update the vnc
        # data in mariadb
        pid_scheduler, errors = get_scheduler_id_pid(hostname)
        if not errors:
            for index, vnc_data in vnc_dict.items():
                pid = str(vnc_data['pid'])
                if pid in pid_scheduler.keys():
                    vnc_data.update(
                        {'scheduler_id': pid_scheduler[pid]['scheduler_id'],
                         'job_id': pid_scheduler[pid]['job_id']})
                else:
                    vnc_data.update(
                        {'scheduler_id': 0,
                         'job_id': 0})
                node.vnc.update_or_create(
                    index=index,
                    defaults={"detail": vnc_data})

    delete_closed_vnc(node, vnc_dict)


def cmp_vnc_details(new_vncs, old_vncs):
    repull_flag = False
    old_vnc_detail = []
    new_vnc_detail = []
    for old_vnc in old_vncs:
        port = old_vnc['detail']['port']
        pid = old_vnc['detail']['pid']
        old_vnc_detail.append('{}-{}'.format(port, pid))
    for new_vnc in new_vncs.values():
        port = new_vnc['port']
        pid = new_vnc['pid']
        new_vnc_detail.append('{}-{}'.format(port, pid))

    for port_pid in new_vnc_detail:
        if port_pid not in old_vnc_detail:
            repull_flag = True
            break

    if repull_flag:
        logger.info(
            "repull the pid/jobid mapping,the old vnc data in mariadb:{},"
            "the new vnc data in icinga:{}".format(
                old_vnc_detail, new_vnc_detail))
    return repull_flag


def delete_closed_vnc(node, vnc_dict):
    update_indexs = []
    # delete the vncs in mariadb which are not in icinga vnc data
    for index, vnc_data in vnc_dict.items():
        update_indexs.append(index)
    node.vnc.exclude(index__in=update_indexs).delete()


def get_scheduler_id_pid(hostname):
    errors = False
    conn = RemoteSSH(hostname)
    node_scheduler_process = NodeSchedulerProcess()
    try:
        pid_job_info = node_scheduler_process.get_process_job_info(
            hostname, conn, scheduler_id=None)
    except Exception as e:
        logger.error(e)
        if "No job steps exist on this node" in str(e):
            errors = False
        else:
            errors = True
        pid_job_info = {}
    finally:
        conn.close()
    return pid_job_info, errors


def parse_vnc(node_metric):
    vncs = node_metric.get("vnc_session", {})
    vnc_dict = delete_status(vncs.get("output"))
    return vnc_dict or {}


def delete_status(output):
    try:
        out = re.sub(r"\[\w+\] - ", "", literal_eval(
            "'{}'".format(output)))
        return json.loads(out)
    except Exception:
        return
