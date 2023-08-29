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
from collections import Counter
from datetime import datetime

from dateutil.parser import parse
from dateutil.relativedelta import relativedelta
from dateutil.tz import tz

from lico.scheduler.base.exception.job_exception import (
    InvalidTimeFormatException, UnknownSubmitTimeException,
)
from lico.scheduler.base.job.job_state import JobState
from lico.scheduler.utils.cmd_utils import exec_oscmd_with_login
from lico.scheduler.utils.host_utils import MEMORY_UNIT

from ..lsf_config import SchedulerConfig

job_state_mapping = {
    "DONE": JobState.COMPLETED,
    "RUN": JobState.RUNNING,
    "ZOMBI": JobState.FAILED,
    "EXIT": JobState.COMPLETED,
    "PEND": JobState.PENDING,
    "WAIT": JobState.PENDING,
    "PROV": JobState.PENDING,
    "FWD_PEND": JobState.PENDING,
    "PSUSP": JobState.HOLD,
    "USUSP": JobState.SUSPENDED,
    "SSUSP": JobState.SUSPENDED
}

logger = logging.getLogger(__name__)


def convert_job_state(lsf_state: str) -> JobState:
    return job_state_mapping.get(lsf_state, JobState.UNKNOWN)


# The timezone depend on run env.
def convert_timestr_2_datetime(
        config: SchedulerConfig, timestr: str
) -> datetime:
    try:
        timestruct = parse(
            timestr,
            dayfirst=config.dayfirst,
            yearfirst=config.yearfirst
        )
    except Exception:
        logger.exception("Time: %s format is not correct.", timestr)
        raise InvalidTimeFormatException

    if '%Y' not in config.timeformat and '%y' not in config.timeformat:
        now = datetime.now()
        delta = relativedelta(days=360)
        if timestruct + delta < now:
            timestruct = timestruct + relativedelta(years=1)
        elif timestruct - delta > now:
            timestruct = timestruct - relativedelta(years=1)

    return timestruct.replace(tzinfo=tz.tzlocal())


# return memory size, unit is KB.
def convert_memory(memory: str) -> float:
    if not memory:
        return 0
    unit = memory.split()[1][0]
    val = float(memory.split()[0])
    unit_size = MEMORY_UNIT[unit]
    size = val * unit_size

    return size


def convert_hosts(hosts_str) -> dict:
    # hosts_str format:
    # old:     lsfnode1:lsfnode1:lsfnode2
    # new:     2*lsfnode1:1*lsfnode2
    host_dict = {}

    host_pattern = re.compile(r'((?P<num>\d+)\*)?(?P<hostname>.*)')
    for host_str in hosts_str.strip().split(':'):
        if host_pattern.match(host_str):
            pattern_dict = host_pattern.search(host_str).groupdict()
            hostname = pattern_dict['hostname']
            num = int(pattern_dict['num']) if pattern_dict['num'] else 1
            if hostname:
                if hostname in host_dict:
                    host_dict[hostname] += num
                else:
                    host_dict[hostname] = num
    return host_dict


def convert_gpu_alloc(gpu_alloc_str) -> dict:
    # gpu_alloc_str format:
    # 1. shield-c2:0,1,0,1,0,1,0,1,0,1;shield-c1:1,0,1,0,1,0,1,0,1,0
    # 2. c2:0:3/3,0:3/3

    gpu_dict = {}
    if not gpu_alloc_str.strip():
        return gpu_dict
    try:
        for gpu_str in gpu_alloc_str.strip().split(';'):
            hostname, gpu_list_str = gpu_str.split(':', 1)

            gpu_dict[hostname] = {}

            gpu_list = gpu_list_str.split(',')
            for i, g in enumerate(gpu_list):
                if ":" not in g:
                    gpu_list[i] = g + ":gpu"

            gpu_counter = Counter([g.split(":", 1)[-1] for g in set(gpu_list)])
            for gpu_type, gpu_count in gpu_counter.items():
                gpu_dict[hostname][gpu_type] = gpu_count

    except Exception:
        logger.warning(f"parse gpu info failed. Content: {gpu_alloc_str}")

    # gpu_dict example: {'c2': {'3/3': 1, 'gpu': 1}, 'c1': {'gpu': 2}}
    # key gpu stands for no-type
    return gpu_dict


def get_job_submit_datetime(scheduler_id, config):
    rc, out, err = exec_oscmd_with_login(
        ["bjobs", '-UF', scheduler_id],
        timeout=config.timeout
    )

    job_info = [s for s in out.decode().splitlines() if s.strip() != '']
    reg_obj = map(lambda s: re.search(r'^(.*): Submitted from', s), job_info)

    for obj in reg_obj:
        if obj is not None:
            if obj.groups()[0].lower() == "unknown":
                logger.error("Fail to get job submit time. Job id: %s",
                             scheduler_id)
                raise UnknownSubmitTimeException

            return convert_timestr_2_datetime(config, obj.groups()[0])

    logger.error("Fail to get job submit time. Job id: %s", scheduler_id)
    raise UnknownSubmitTimeException
