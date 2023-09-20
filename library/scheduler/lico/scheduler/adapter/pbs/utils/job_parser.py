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

import logging
import re
from collections import defaultdict

from dateutil.parser import parse
from dateutil.tz import tzlocal

from lico.scheduler.base.job.job import Job
from lico.scheduler.base.job.job_running import JobRunning
from lico.scheduler.base.job.job_state import JobState
from lico.scheduler.base.tres.trackable_resource import TrackableResource
from lico.scheduler.base.tres.trackable_resource_type import (
    TrackableResourceType,
)

from ..pbs_job_identity import JobIdentity

logger = logging.getLogger(__name__)


def is_number(value):
    try:
        float(value)
        return True
    except ValueError:
        return False


def parse_job_info(  # noqa: C901
        jobid: str,
        job_info: dict,
        config
) -> Job:
    job = Job()

    job.name = job_info['Job_Name']
    job.submit_time = convert_timestr_2_datetime(job_info['ctime'])
    if job_info.get('stime') is not None:
        job.start_time = convert_timestr_2_datetime(job_info['stime'])
    if job_info['job_state'] in ('E', 'F', 'X'):
        job.end_time = convert_timestr_2_datetime(job_info['mtime'])
        # job.runtime = int((job.end_time - job.start_time).total_seconds())
        job.runtime = -1
    job.submitter_username = job_info['Variable_List']['PBS_O_LOGNAME']
    state_map = {
        'B': JobState.RUNNING,  # array job has at least on job running
        'E': JobState.COMPLETING,  # exiting after having run
        'F': JobState.COMPLETED,  # finished
        'H': JobState.HOLD,  # held
        'M': JobState.REQUEUED,  # moved to another server
        'Q': JobState.PENDING,  # queued
        'R': JobState.RUNNING,  # running
        'S': JobState.SUSPENDED,  # suspended
        'T': JobState.REQUEUED,  # being moved to new location
        'U': JobState.PENDING,  # job suspended due to keyboard activity
        # waiting for its submitter assigned start time to be reached
        'W': JobState.PENDING,
        # subjob has completed execution or has been deleted
        'X': JobState.COMPLETED
    }
    exec_hosts = job_info.get('exec_host')
    job.state = state_map.get(job_info['job_state'], JobState.UNKNOWN)
    res_list = job_info.get('Resource_List', {})
    res_list['mem'] = job_info.get('resources_used', {}).get('mem', '0kb')
    res_list['nodect'] = len(
        list({host.split('/')[0] for host in exec_hosts.split('+')})
    ) if exec_hosts is not None else res_list.get('nodect')
    job.resource_list = get_resource(res_list)
    job.running_list = []
    if exec_hosts is not None:
        host_count = defaultdict(int)
        for hostinfo in exec_hosts.split("+"):
            host_num = hostinfo.split("*")
            if len(host_num) == 1:
                host_num.append("1")
            host = host_num[0].split("/")[0]
            host_count[host] += int(host_num[1])
        count_hosts = defaultdict(list)
        for host, count in host_count.items():
            count_hosts[count].append(host)
        for count, hosts in count_hosts.items():
            res_list["ncpus"] = count * len(hosts)
            job.running_list.append(
                JobRunning(hosts, get_resource(res_list, host_num=len(hosts)))
            )
    submit_host = job_info['Submit_Host']
    job.workspace_path = job_info['Variable_List']['PBS_O_WORKDIR']
    job.standard_output_filename = job_info['Output_Path'].replace(
        submit_host+':', '')
    job.error_output_filename = job_info['Error_Path'].replace(
        submit_host+':', '')
    job.queue_name = job_info['queue']
    job.comment = job_info['Variable_List'].get('LiCO_JOB_ID', '')

    job.identity = JobIdentity(
        scheduler_id=jobid,
        submit_time=job.submit_time
    )
    priority = job_info.get('Priority', '')
    job.priority = str(priority) if is_number(priority) else ''

    return job


def convert_string_to_bytes(string) -> int:
    """ Converts a given string to integer bytes

    Eg:
        100kb -> 102400 (bytes)
        100mb -> 104857600 (bytes)
        100gb -> 107374182400 (bytes)
    """
    string = string.lower()

    data = {'b': 1, 'kb': 1024, 'mb': 1024**2, 'gb': 1024**3, 'tb': 1024**4}

    try:
        value, unit = re.search(r'(\d+)(.*)', string).groups()
    except Exception as exc:
        logger.debug(str(exc))
        value, unit = 0, 'b'

    return data.get(unit, 0) * int(value)


def convert_timestr_2_datetime(time_str: str):
    try:
        return parse(time_str).replace(tzinfo=tzlocal())
    except Exception:
        logger.warning('Fail to convert time str to datetime')
        return None


def get_resource(data, host_num=1):
    """
    Args:
        data (dict) : A dict as provided by pbs qsub command with json output
        host_num: job exec host num

    Example:
        {
            "ncpus":20,
            "ngpus":2,
            "nodect":2,
            "place":"free",
            "select":"2:ncpus=10:ngpus=1",
            "walltime":"24:00:00"
        },
    """
    trackable_resource_type_map = {
        'mem': TrackableResourceType.MEMORY,
        'ncpus': TrackableResourceType.CORES,
        'nodect': TrackableResourceType.NODES,
        'ngpus': TrackableResourceType.GRES,
    }
    resource_list = []
    for k, v in data.items():
        code = None
        _type = trackable_resource_type_map.get(k)
        if _type is None:
            logger.debug(f'Undefined resource type {k}. Skipping ...')
            continue

        if _type == TrackableResourceType.MEMORY:
            count = convert_string_to_bytes(v) / 1024**2  # MB
        elif _type == TrackableResourceType.GRES:
            code, count = 'gpu', float(v)
        else:
            count = int(v)
        if round(count/host_num, 2):
            resource_list.append(TrackableResource(
                type=_type, code=code, count=round(count/host_num, 2)))
    return resource_list
