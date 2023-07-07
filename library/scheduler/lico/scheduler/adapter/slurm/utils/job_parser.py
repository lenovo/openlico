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
import time
from collections import defaultdict
from datetime import datetime, timedelta
from subprocess import CalledProcessError, check_output  # nosec B404
from typing import Dict, List, Optional

from dateutil.parser import parse
from dateutil.tz import tzlocal

from lico.scheduler.base.exception.job_exception import NodeListParseException
from lico.scheduler.base.job.job import Job
from lico.scheduler.base.job.job_running import JobRunning
from lico.scheduler.base.job.job_state import JobState
from lico.scheduler.base.tres.trackable_resource import TrackableResource
from lico.scheduler.base.tres.trackable_resource_type import (
    TrackableResourceType,
)
from lico.scheduler.utils.cmd_utils import exec_oscmd
from lico.scheduler.utils.host_utils import MEMORY_UNIT

from ..slurm_job_identity import JobIdentity

logger = logging.getLogger(__name__)
FAILED_TO_PARSE_MEM = -1


def convert_runtime_2_seconds(time_length: str) -> int:
    if time_length.strip() == "UNLIMITED":
        return 0
    time_list = [int(i) for i in reversed(re.findall(r'\d+', time_length))]
    default_value = {
        "days": 0,
        "hours": 0,
        "minutes": 0,
        "seconds": 0
    }
    keys_list = ["seconds", "minutes", "hours", "days"]
    for index, time_value in enumerate(time_list):
        default_value[keys_list[index]] = time_value

    times = timedelta(
        days=default_value["days"],
        hours=default_value["hours"],
        minutes=default_value["minutes"],
        seconds=default_value["seconds"])
    return int(times.total_seconds())


def convert_timestr_2_datetime(time_str: str) -> Optional[datetime]:
    if time_str == 'Unknown':
        return None
    try:
        return parse(time_str).replace(tzinfo=tzlocal())
    except Exception:
        logger.warning('Fail to convert time str to datetime')
        return None


def expand_host_list(hosts_str: str) -> List:
    hosts = []
    bracket_num = 0
    part_host = ""
    for single_char in hosts_str + ",":
        if single_char == "," and bracket_num == 0:
            # Comma at top level, split!
            if part_host:
                hosts.extend(expand_slurm(part_host))
            part_host = ""
        else:
            part_host += single_char
        if single_char == "[":
            bracket_num += 1
        elif single_char == "]":
            bracket_num -= 1
        if bracket_num > 1 or bracket_num < 0:
            raise NodeListParseException("Brackets unmatched.")
    if bracket_num > 0:
        raise NodeListParseException("Brackets unmatched.")
    return list(set(hosts))


def expand_slurm(need_expand: str) -> List:
    if need_expand == "":
        return [""]
    m = re.match(r'([^,\[]*)(\[[^\]]*\])?(.*)', need_expand)
    (prefix, range_list, rest) = m.group(1, 2, 3)

    rest_expand = expand_slurm(rest)

    if not range_list:
        curr_expand = [prefix]
    else:
        curr_expand = []
        for range_slurm in range_list[1:-1].split(","):
            results = expand_slurm_range(prefix, range_slurm)
            curr_expand.extend(results)
    if len(curr_expand) * len(rest_expand) > 10000:
        raise NodeListParseException("Contains too many nodes.")
    return [curr_part + rest_part
            for curr_part in curr_expand
            for rest_part in rest_expand]


def expand_slurm_range(prefix: str, range_slurm: str) -> List:
    m = re.match(r'^[0-9]+$', range_slurm)
    if m:
        return ["%s%s" % (prefix, range_slurm)]
    match_re = re.match(r'^([0-9]+)-([0-9]+)$', range_slurm)
    if not match_re:
        raise NodeListParseException("Invalid range.")
    (exp_low, exp_high) = match_re.group(1, 2)
    low = int(exp_low)
    high = int(exp_high)
    width = len(exp_low)
    if high < low:
        raise NodeListParseException("Start greater than End.")
    elif high - low > 10000:
        raise NodeListParseException("Contains too many nodes.")
    results = []
    for i in range(low, high + 1):
        results.append("%s%0*d" % (prefix, width, i))
    return results


def convert_tres_dict_2_obj(gres_hosts: dict, nodes_count=1):
    # gres_host example:
    # {
    #   "gpu": {"no_type":4, "2g.10gb":2, '3g.20gb':4},
    #   "fpga": {}
    # }
    gres_list = []
    gres_list_append = gres_list.append
    for key, value in gres_hosts.items():
        if not len(value):
            continue
        for k, v in value.items():
            if not v:
                continue
            if k == 'no_type':
                gres_list_append(TrackableResource(
                    type=TrackableResourceType.GRES,
                    code=key,
                    count=v * nodes_count,
                ))
            else:
                gres_list_append(TrackableResource(
                    type=TrackableResourceType.GRES,
                    code=key,
                    count=v * nodes_count,
                    spec=k
                ))
    return gres_list


def get_job_running_list(
        hosts: list, average_cpu_num: int,
        max_mem_val: float, gres_hosts: dict
) -> List[JobRunning]:
    # gres_hosts : {'gpu': {'2g.10gb': 1.0}}
    per_host_resource_list = []
    res_append = per_host_resource_list.append

    if average_cpu_num:
        res_append(TrackableResource(
            type=TrackableResourceType.CORES,
            count=average_cpu_num
        ))
    if max_mem_val:
        res_append(TrackableResource(
            type=TrackableResourceType.MEMORY,
            count=round(float(max_mem_val / len(hosts)), 2)
        ))

    per_host_resource_list.extend(convert_tres_dict_2_obj(gres_hosts))

    return [JobRunning(hosts, per_host_resource_list)]


def get_job_resource_list(
        nodes_count: int, average_cpu_num: int,
        max_mem_val: float, gres_hosts: dict
) -> List[TrackableResource]:
    resource_list = []
    res_append = resource_list.append

    if max_mem_val:
        res_append(TrackableResource(
            type=TrackableResourceType.MEMORY,
            count=max_mem_val
        ))

    if nodes_count:
        res_append(TrackableResource(
            type=TrackableResourceType.NODES,
            count=nodes_count
        ))

        if average_cpu_num:
            res_append(TrackableResource(
                type=TrackableResourceType.CORES,
                count=average_cpu_num * nodes_count
            ))

        resource_list.extend(convert_tres_dict_2_obj(gres_hosts, nodes_count))

    return resource_list


def parse_gres_str(gres: str) -> Dict:
    gres_dict = {}
    gres_list = [gres_item for gres_item in gres.split(',')]

    for gres_item_str in gres_list:
        g_list = re.split(':|/|=', gres_item_str)

        if g_list[0] == 'gres':
            g_list = g_list[1:]
        if not is_number(g_list[-1]):
            g_list += ['1']
        if len(g_list) < 2 or g_list[0] != 'gpu':
            continue
        if len(g_list) == 2:
            g_list.insert(1, 'no_type')

        if len(g_list) != 3:
            logger.error(f"Cannot parse gres item:{gres_item_str}")
            continue

        # g_list : ['gpu', '2g.10gb', '1']
        if g_list[0] not in gres_dict:
            gres_dict[g_list[0]] = defaultdict(int)
        gres_dict[g_list[0]][g_list[1]] += float(g_list[2])

    for k, v in gres_dict.items():
        if 'no_type' in v and len(v) > 1:
            v.pop('no_type')

    return gres_dict


def convert_tres_gres_count(gres: str) -> Dict:
    # TRES=cpu=152,node=1,billing=152,
    #      gres/gpu=6,gres/gpu:2g.10gb=4,gres/gpu:3g.20gb=2
    logger.debug(f"Convert tres str: {gres}")

    gres_dict = {}
    node_num = 1

    if gres != 'Unknown' and len(gres) > 0:
        gres_list = [gres_item.split('=') for gres_item in gres.split(",")]

        for item in gres_list:
            if len(item) < 2:
                continue

            if item[0] == 'node':
                node_num = int(item[-1])
                break

        gres_dict = parse_gres_str(gres)
        for k, v in gres_dict.items():
            gres_dict[k] = {
                gres_type: round(gres_total/node_num, 2)
                for gres_type, gres_total in v.items()
            }
    # gres_host example:
    # {
    #   "gpu": {"no_type":4, "2g.10gb":2, '3g.20gb':4},
    # }
    return gres_dict


def convert_gres_count(gres: str) -> Dict:
    # TresPerNode=gpu:2g.10gb:1
    logger.debug(f"Convert gres str: {gres}")

    gres_dict = {}
    if gres != 'Unknown' and len(gres) > 0:
        gres_dict = parse_gres_str(gres)
    # gres_host example:
    # {
    #   "gpu": {"no_type":4, "2g.10gb":2, '3g.20gb':4},
    # }
    return gres_dict


# return memory size, unit is KB.
def convert_memory(memory: str) -> float:
    if memory == 'Unknown' or memory == '0' or not memory:
        return 0

    unit = memory[-1]
    val = float(memory[0:-1])
    size = val * MEMORY_UNIT[unit]
    return size


def convert_time(time_str: str) -> int:
    # The format of this fields output is as follows:
    # [DD-[HH:]]MM:SS
    # as defined by the following:
    #    DD    days
    #    hh    hours
    #    mm    minutes
    #    ss    seconds
    if time_str == "UNLIMITED":
        return 0

    if time_str and time_str != 'Unknown':
        seconds = 0
        dd_vals = time_str.split('-')
        if len(dd_vals) == 2:
            seconds += int(dd_vals[0]) * 24 * 3600
            ss_vals = dd_vals[1].split(':')
        else:
            ss_vals = time_str.split(':')
        if len(ss_vals) == 3:
            seconds += int(ss_vals[0]) * 3600
            seconds += int(ss_vals[1]) * 60
            seconds += int(ss_vals[2])
        else:
            seconds += int(ss_vals[0]) * 60
            seconds += int(ss_vals[1])
        return seconds
    return 0


def parse_slurm_mem_info(raw_info: str) -> dict:
    job_mem = {}
    for step_info in raw_info.decode().splitlines():
        if step_info.strip() != '':
            step_content = [j.strip() for j in step_info.strip("|").split("|")]
            job_mem[step_content[0]] = step_content
    return job_mem


# return memory size, unit is KB.
def calculate_step_mem(
        step_mem: float,  # unit: KB
        step_ntasks: str,
        step_elapsed: int,
        job_elapsed_time: int
) -> float:
    try:
        mem_value = step_mem * int(step_ntasks)
        pct_time = step_elapsed / job_elapsed_time
        return round(mem_value * pct_time, 2)
    except Exception:
        logger.exception("Parse memory value error")
        return FAILED_TO_PARSE_MEM


def get_job_memory(
        jobid: str,
        retry_count=0,
        retry_interval=0.5
) -> float:
    """
    Command sstat is only used for a running job/step,
    and can't display the Elapsed value;
    command sacct could not dispaly the AveRSS value for a running step.
    """
    for i in range(retry_count):
        all_step_mem, all_step_info, running_step_info = [], {}, {}
        sstat_args = ["sstat", "--noheader", "-a", "-p",
                      "--format=JobID,AveRSS,NTasks",
                      "-j", jobid]
        sacct_args = ["sacct", "--noheader", "-a", "-p",
                      "--format=JobIdRaw,AveRSS,NTasks,Elapsed",
                      "-j", jobid]

        try:
            running_step_raw_info = check_output(sstat_args)  # nosec B603
            all_step_raw_info = check_output(sacct_args)  # nosec B603
        except CalledProcessError as e:
            logger.warning(
                'Get job memory failed, the cmd is {0}, the error is {1}'
                .format(e.cmd, e.stderr))
            return 0
        all_step_info = parse_slurm_mem_info(all_step_raw_info)
        running_step_info = parse_slurm_mem_info(running_step_raw_info)

        if jobid in all_step_info:
            job_elapsed_time = all_step_info[jobid][-1]
            if job_elapsed_time in ["00:00", "00:00:00"]:
                continue

        for step_id, step_content in all_step_info.items():
            # When a job is submitted in the sbatch.script format.
            # The first row cannot display the AveRss value,
            # which JobID value just is exactly equal to JobId without StepId.
            # while other rows' values are like JobId.StepId.

            # exclude extra array job or heterogeneous job
            if jobid not in step_id:
                continue
            if step_id == jobid and not step_content[1]:
                continue
            if step_id in running_step_info and not step_content[1]:
                step_content[1] = running_step_info[step_id][1]
                step_content[2] = running_step_info[step_id][2]
            single_step_mem = calculate_step_mem(
                step_mem=convert_memory(step_content[1]),
                step_ntasks=step_content[2],
                step_elapsed=convert_time(step_content[3]),
                job_elapsed_time=convert_time(job_elapsed_time))
            if single_step_mem == FAILED_TO_PARSE_MEM:
                return 0
            all_step_mem.append(single_step_mem)

        if len(all_step_mem) > 0:
            return round(sum(all_step_mem) / 1024, 2)  # unit: MB
        if retry_count:
            time.sleep(retry_interval)
    else:
        logger.info('Memory is null until slurm prepares the data.')
        return 0


def try_int(value):
    # value may be <min_count>[-<max_count>]. e.g. '5-5'
    if '-' in value:
        value = value.split('-')[-1]
    return int(value) if value.isdigit() else 0


def is_number(value):
    try:
        float(value)
        return True
    except ValueError:
        return False


def parse_job_info(  # noqa: C901
        jobid: str,
        job_info: List[str],
        config,
        query_memory=True
) -> Job:
    job = Job()

    split_re = re.compile(r'(?<= |\t)(\S+?)=')

    node_lists = ""
    cpus_count = 0
    nodes_count = 0
    num_tasks = 0
    num_cpus_per_task = 0
    gres_dict = {}
    min_cpus_node = 0
    end_time_raw_value = ""
    for line in job_info:
        params = re.split(split_re, line)
        for index in range(1, len(params), 2):
            key = params[index].strip()
            value = params[index + 1].strip()

            if key == "JobName":
                job.name = value
            elif key == "JobState":
                job.state = JobState[value]
            elif key == "RunTime":
                job.runtime = convert_runtime_2_seconds(value)
            elif key == "SubmitTime":
                job.submit_time = convert_timestr_2_datetime(value)
            elif key == 'StartTime':
                job.start_time = convert_timestr_2_datetime(value)
            elif key == 'EndTime':
                end_time_raw_value = value
                job.end_time = convert_timestr_2_datetime(value)
            elif key == 'Partition':
                job.queue_name = value
            elif key == 'StdOut':
                job.standard_output_filename = value
            elif key == 'StdErr':
                job.error_output_filename = value
            elif key == 'UserId':
                job.submitter_username = value.split("(")[0]
            elif key == 'WorkDir':
                job.workspace_path = value
            elif key == "Comment":
                job.comment = value
            elif key == "TimeLimit":
                job.time_limit = convert_runtime_2_seconds(value)
            elif key == "ExitCode":
                job.exit_code = value
            elif key == "Priority":
                job.priority = value if is_number(value) else ''
            elif key == 'NodeList':
                node_lists = value
            elif key == 'NumNodes':
                nodes_count = try_int(value)
            elif key == 'NumCPUs':
                cpus_count = try_int(value)
            elif key == 'NumTasks':
                num_tasks = try_int(value)
            elif key == 'CPUs/Task':
                num_cpus_per_task = try_int(value)
            elif key == 'TRES':
                gres_dict = convert_tres_gres_count(value)
            elif key == 'Gres' or key == 'TresPerNode':
                if not gres_dict:
                    gres_dict = convert_gres_count(value)
            elif key == 'MinCPUsNode':
                min_cpus_node = try_int(value)

    logger.debug(
        f"Pre parse job resource. node_lists: {node_lists}; "
        f"num_cpus_per_task: {num_cpus_per_task}; "
        f"nodes_count: {nodes_count}"
    )

    if num_cpus_per_task and nodes_count:
        average_cpu_num = max(
            cpus_count, num_tasks * num_cpus_per_task
        ) / nodes_count
        average_cpu_num = min_cpus_node \
            if not average_cpu_num else average_cpu_num

        # slurm may not return memory immediately
        # so add retry to get job memory
        ave_mem = 0
        if query_memory or job.state in JobState.get_final_state():
            ave_mem = get_job_memory(
                    jobid,
                    retry_count=config.memory_retry_count,
                    retry_interval=config.memory_retry_interval_second
                )

        if node_lists and node_lists != '(null)':
            hosts = expand_host_list(node_lists)

            # origin nodes_count is parsed by <min_count>[-<max_count>],
            # may be exceed real nodes count, so overwrite nodes_count by
            # parsing node_list
            nodes_count = len(hosts)

            job.running_list = get_job_running_list(
                hosts, average_cpu_num, ave_mem, gres_dict
            )

        job.resource_list = get_job_resource_list(
            nodes_count, average_cpu_num, ave_mem, gres_dict
        )

    if job.state in JobState.get_final_state() \
            and end_time_raw_value.lower() == 'unknown':
        job.state = JobState.RUNNING

    if job.submit_time is None:
        logger.warning("Fail to get job submit time. Job id: %s", jobid)

    job.identity = JobIdentity(
        scheduler_id=jobid,
        submit_time=job.submit_time
    )

    return job


def get_job_submit_datetime(job_id, timeout):
    rc, out, err = exec_oscmd(
        args=["scontrol", "show", "jobs", str(job_id)],
        timeout=timeout
    )
    reg = re.search(r'SubmitTime=(?P<submit_time>\S+)', out.decode())

    submit_time_dt_str = reg.groupdict()['submit_time']
    if submit_time_dt_str.lower() == 'unknown' or not submit_time_dt_str:
        logger.error("Fail to get job submit time. Job id: %s", job_id)

    return convert_timestr_2_datetime(submit_time_dt_str)


def get_job_alter_id(job_id, timeout):
    rc, out, err = exec_oscmd(
        args=["scontrol", "show", "jobs", str(job_id)],
        timeout=timeout
    )
    job_info_msg = 'JobId={0}'.format(str(job_id))
    job_info = [s for s in out.decode().splitlines()
                if s.strip().startswith(job_info_msg)]
    if len(job_info) == 1 and 'ArrayJobId' in job_info[0]:
        array_job_id = None
        array_task_id = None
        split_re = re.compile(r'(?<= |\t)(\S+?)=')
        params = re.split(split_re, job_info[0])
        for index in range(1, len(params), 2):
            key = params[index].strip()
            value = params[index + 1].strip()
            if key == 'ArrayJobId':
                array_job_id = value
            elif key == 'ArrayTaskId':
                array_task_id = value
                break
        if array_job_id and array_task_id and '-' not in array_task_id:
            return f'{array_job_id}_{array_task_id}'
    return job_id
