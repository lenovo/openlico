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
from collections import defaultdict
from os import path
from typing import List

from lico.scheduler.base.job.job import Job
from lico.scheduler.base.job.job_running import JobRunning
from lico.scheduler.base.tres.trackable_resource import TrackableResource
from lico.scheduler.base.tres.trackable_resource_type import (
    TrackableResourceType,
)

from ..lsf_config import SchedulerConfig
from ..lsf_job_identity import JobIdentity
from .utils import (
    convert_gpu_alloc, convert_hosts, convert_job_state, convert_memory,
    convert_timestr_2_datetime,
)

logger = logging.getLogger(__name__)


def parse_job_info(
        scheduler_id: str,
        job_dict: dict,
        config: SchedulerConfig
) -> Job:
    job = Job()

    job, resource_o = parse_info_o(job, job_dict.get('info_o', {}))

    job, resource_uf = parse_info_uf(
        job,
        job_dict.get('info_uf', []),
        config,
        resource_o.get("node", list())
    )

    job.resource_list, job.running_list = parse_resource(
        resource_uf, resource_o)

    if job.end_time and job.start_time and not job.runtime:
        job.runtime = int((job.end_time - job.start_time).total_seconds())

    job.identity = JobIdentity(
        scheduler_id=scheduler_id,
        submit_time=job.submit_time
    )
    return job


def parse_info_uf(job, info_uf, config, nodes=list()):
    sub_pattern = re.compile(r'^(.*): Submitted from.*')
    start_pattern = re.compile(r'^(.*): (\[.+\] started|Started).*')
    comp_pattern = re.compile(r'^(.*; )?(.*): Completed.*')
    done_pattern = re.compile(r'^(.*): Done successfully.*')

    # running job gpu resource
    gres_block_start = "EXTERNAL MESSAGES"
    gres_block_end = "RESOURCE REQUIREMENT DETAILS"
    gres_block_gpu = "GPU REQUIREMENT DETAILS"

    in_gpu_block = False
    in_gpu_mig_block = False
    gpu_content = []

    for line in info_uf:
        if gres_block_start in line:
            in_gpu_block = True
        if gres_block_end in line:
            in_gpu_block = False
        if in_gpu_block and line.strip():
            gpu_content.append(line.strip())
        # used mig
        if gres_block_gpu in line:
            in_gpu_mig_block = True
        if in_gpu_mig_block and in_gpu_block is False:
            gpu_content.append(line.strip())

        # parse job basic info
        if sub_pattern.match(line):
            job.submit_time = convert_timestr_2_datetime(
                config,
                sub_pattern.search(line).groups()[0]
            )
        elif start_pattern.match(line):
            job.start_time = convert_timestr_2_datetime(
                config,
                start_pattern.search(line).groups()[0]
            )
        elif comp_pattern.match(line):
            job.end_time = convert_timestr_2_datetime(
                config,
                comp_pattern.search(line).groups()[1]
            )
        elif done_pattern.match(line):
            job.end_time = convert_timestr_2_datetime(
                config,
                done_pattern.search(line).groups()[0]
            )

    if job.end_time and not job.start_time:
        job.start_time = job.end_time

    gpu_key, gpu_dict = parse_gpu_block(gpu_content, nodes)
    resource = {
        gpu_key: gpu_dict
    }
    return job, resource


def parse_gpu_block(gpu_content: List[str], gpu_mig_host):
    # gpu_dict = {<host_name>: <gpu_num>}
    gpu_dict = {}
    gpu_key = 'gpu'
    if len(gpu_content) < 3:
        return gpu_key, gpu_dict

    msg_start_index = None
    msg_end_index = None
    gpu_num = None
    mig_dict = {}
    if "GPU REQUIREMENT DETAILS" in gpu_content[0]:
        # gpu_dict:{'c2': {'2/2': 1}}
        for index, line in enumerate(gpu_content):
            try:
                if "Effective" in line:
                    for mig_info in gpu_content[index].split(":"):
                        if "num" in mig_info.split("=")[0]:
                            gpu_num = mig_info.split("=")[1]
                        if "mig" in mig_info.split("=")[0]:
                            mig_dict[mig_info.split("=")[1]] = int(gpu_num)
                            for host in gpu_mig_host:
                                gpu_dict[host] = dict(mig_dict)
            except Exception:
                logger.warning(
                    f"parse gpu info failed. Content: {gpu_content}"
                )
        gpu_key = 'mig_gpu'
    else:
        # gpu_dict:{"c1":2}
        for i, line in enumerate(gpu_content[1:]):
            try:
                if i == 0:
                    msg_start_index = line.index('MESSAGE')
                    msg_end_index = line.index('ATTACHMENT')
                else:
                    message = line[msg_start_index:msg_end_index]
                    for gpu_host in message.split(';'):
                        if gpu_host.strip() and 'gpus' in gpu_host:
                            gpu_fields = gpu_host.strip().split(':gpus=', 1)
                            gpu_dict[gpu_fields[0]] = \
                                len(gpu_fields[1].split(','))
            except Exception:
                logger.warning(f"parse gpu info failed. Content: {line}")
        gpu_key = 'gpu'
    return gpu_key, gpu_dict


def parse_info_o(job, info_o):
    if "ERROR" in info_o:
        return job, {'node': [], 'memory': 0, 'cpu': {}}

    job.name = info_o.get('JOB_NAME')
    job.submitter_username = info_o.get('USER')
    job.state = convert_job_state(info_o.get('STAT'))
    job.workspace_path = info_o.get('EXEC_CWD')
    job.standard_output_filename = path.join(
        job.workspace_path, info_o.get('OUTPUT_FILE'))
    job.error_output_filename = path.join(
        job.workspace_path, info_o.get('ERROR_FILE'))
    job.exit_code = info_o.get('EXIT_CODE')
    job.queue_name = info_o.get('QUEUE')
    if info_o.get('RUNTIMELIMIT'):
        job.time_limit = int(float(info_o.get('RUNTIMELIMIT'))) * 60  # seconds
    job.comment = info_o.get('JOB_DESCRIPTION')

    runtime_str = info_o.get('RUN_TIME', '')
    runtime_pattern = re.compile(r'(\d+) second\(s\)')
    if runtime_pattern.match(runtime_str):
        job.runtime = int(runtime_pattern.search(runtime_str).groups()[0])

    host_dict = convert_hosts(info_o.get('ALLOC_SLOT', ''))

    resource = {
        'node': host_dict.keys(),
        # total memory (MB)
        'memory': round(convert_memory(info_o.get('AVG_MEM'))/1024, 2),
        'cpu': host_dict,
        'gpu': convert_gpu_alloc(info_o.get('GPU_ALLOC', ''))
    }
    return job, resource


def parse_resource(resource_uf, resource_o):
    '''
    resource: {
        "node": [<hostname>, ...]
        "memory": <total_memory_mb>,
        "cpu": {<hostname>: <cpu_num>, ...},
        "gpu": {<hostname>: <cpu_num>, ...}
    }
    '''
    node_list = resource_o['node']
    resource_dict = {}

    cpu_total = 0
    mem_total = 0
    gpu_total = defaultdict(int)

    if node_list:
        # parse running or completed job resource

        resource_dict = {node: [0, {}, 0] for node in node_list}
        #                     [<cpu>,<gpu>,<mem>]

        cpu_dict = resource_o['cpu']
        if cpu_dict:
            cpu_total = sum(cpu_dict.values())
            mem_total = resource_o['memory']

            for hostname, cpu_count in cpu_dict.items():
                resource_dict[hostname][0] = cpu_count
                resource_dict[hostname][2] = round(
                    mem_total * cpu_count / cpu_total, 2)
    else:
        # parse queuing job resource
        # resource_uf["node"] =
        # resource_uf["cpu"] =
        # resource_uf["memory"] =
        pass

    gpu_alloc_dict = {}
    if resource_uf.get('mig_gpu'):
        # e.g. {'c1': {'2/2': 1}, 'c2': {'2/2': 1}}
        gpu_alloc_dict = resource_uf['mig_gpu']
    else:
        if resource_o.get('gpu'):
            # e.g. {'c1': {'gpu': 2}, 'c2': {'gpu': 1}}
            gpu_alloc_dict = resource_o['gpu']
        elif resource_uf.get('gpu'):
            # e.g. {'c1': 2, 'c2': 1}
            gpu_alloc_dict = resource_uf['gpu']

    format_gpu_dict(gpu_alloc_dict)

    # gpu_alloc_dict example:
    #     {
    #       'c2': {'gpu': 2, '3/3': 1, '3/2': 1},
    #       'c1': {'gpu': 2}
    #     }
    if gpu_alloc_dict and resource_dict:
        for hostname, gpu_count in gpu_alloc_dict.items():
            try:
                resource_dict[hostname][1] = dict(
                    sorted(gpu_count.items(), key=lambda x: x[0])
                )

                for g_type, g_count in gpu_count.items():
                    gpu_total[g_type] += g_count
            except Exception:
                logger.warning(
                    f'failed to set host: {hostname} gres: {gpu_count}')

    resource_dict = group_by_resource(resource_dict)
    return dict_to_resource_list(
        node_list, cpu_total, mem_total, gpu_total,
        resource_dict
    )


def dict_to_resource_list(
    node_list, cpu_total, mem_total, gpu_total, resource_dict
):
    """
    resource_dict example:
    {'c5,c4': [0, {'2/2': 2}, 0]}
    """
    running_list = []
    for hostnames, resource in resource_dict.items():
        per_host_resource_list = []

        if resource[0]:
            per_host_resource_list.append(TrackableResource(
                type=TrackableResourceType.CORES,
                count=resource[0]
            ))
        if resource[1]:
            for k, v in resource[1].items():
                if not v:
                    continue
                per_host_resource_list.append(
                    TrackableResource(
                        type=TrackableResourceType.GRES,
                        code='gpu',
                        count=v,
                        spec=k if k != 'gpu' else None
                    )
                )
        if resource[2]:
            per_host_resource_list.append(TrackableResource(
                type=TrackableResourceType.MEMORY,
                count=resource[2]
            ))

        running_list.append(JobRunning(
            hosts=hostnames.split(','),
            per_host_resource_list=per_host_resource_list
        ))

    resource_list = []
    if node_list:
        resource_list.append(TrackableResource(
            type=TrackableResourceType.NODES,
            count=len(node_list)
        ))
    if cpu_total:
        resource_list.append(TrackableResource(
            type=TrackableResourceType.CORES,
            count=cpu_total
        ))
    if mem_total:
        resource_list.append(TrackableResource(
            type=TrackableResourceType.MEMORY,
            count=mem_total
        ))
    if gpu_total:
        for g_type, g_count in gpu_total.items():
            if not g_count:
                continue
            resource_list.append(TrackableResource(
                type=TrackableResourceType.GRES,
                code='gpu',
                count=g_count,
                spec=g_type if g_type != 'gpu' else None
            ))

    return resource_list, running_list


def group_by_resource(resource_dict):
    merge_dict = {}
    for hostname, resource in resource_dict.items():
        if str(resource) in merge_dict:
            merge_dict[str(resource)][0] += f",{hostname}"
        else:
            merge_dict[str(resource)] = [hostname, resource]
    return {v[0]: v[1] for v in merge_dict.values()}


def format_gpu_dict(gpu_dict):
    # {"c1":2} ==> {"c1": {"gpu": 2}}
    for hostname, gpu_count in gpu_dict.items():
        if isinstance(gpu_count, int):
            gpu_dict[hostname] = {"gpu": gpu_count}
