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
from collections import defaultdict
from subprocess import check_output

from dateutil.parser import parse
from dateutil.tz import tzlocal

from lico.scheduler.base.exception.job_exception import AcctException
from lico.scheduler.base.job.job import Job
from lico.scheduler.base.job.job_state import JobState

from .slurm_job_identity import JobIdentity
from .utils.job_parser import (
    calculate_step_mem, convert_memory, convert_time, expand_host_list,
    get_job_resource_list, get_job_running_list,
)

logger = logging.getLogger(__name__)

SLURM_SACCT_FIELDS = [
    'JobIDRaw', 'JobName', 'Partition', 'Submit', 'Start', 'End', 'User',
    'State', 'WorkDir', 'Elapsed', 'ExitCode', 'AveRSS', 'NTasks',
    'Comment', 'Timelimit', 'AllocCPUS', 'AllocTRES', 'NodeList', 'AllocNodes'
]

sacct_time_format = '%Y-%m-%dT%H:%M:%S'
delimiter = '|'


class AcctLineReader(object):
    def __init__(self, line):
        self._line = line
        self._line_dict = self.__parse_line()

    def __parse_line(self):
        line_list = self._line.split(delimiter)
        return dict(zip(SLURM_SACCT_FIELDS, line_list))

    def get_value(self, field):
        return self._line_dict.get(field)


class AcctEvent(object):
    def __init__(self, line_reader=None):
        self.line_reader = line_reader
        self.job_id = self.__parse_str(line_reader.get_value('JobIDRaw'))
        self.job_name = self.__parse_str(line_reader.get_value('JobName'))
        self.num_processors = self.__parse_integer(
            line_reader.get_value('AllocCPUS'))
        self.gres_hosts = self.__convert_tres_2_dict(
            line_reader.get_value('AllocTRES'))
        self.submit_time = self.__convert_timestr_2_datetime(
            line_reader.get_value('Submit'))
        self.term_time = self.__convert_timestr_2_datetime(
            line_reader.get_value('End'))
        self.start_time = self.__convert_timestr_2_datetime(
            line_reader.get_value('Start'))
        self.user_name = self.__parse_str(line_reader.get_value('User'))
        self.queue = self.__parse_str(line_reader.get_value('Partition'))
        self.idx = 0
        self.ntasks = self.__parse_integer(line_reader.get_value('NTasks'))
        self.avg_mem = convert_memory(line_reader.get_value('AveRSS'))
        self.run_time = convert_time(line_reader.get_value('Elapsed'))
        self.exit_code = self.__parse_str(line_reader.get_value('ExitCode'))
        self.state = self.__parse_job_state(line_reader.get_value("State"))
        self.workdir = self.__parse_str(line_reader.get_value('WorkDir'))
        self.node_list = self.__parse_str(line_reader.get_value('NodeList'))
        self.nodes_count = self.__parse_integer(
            line_reader.get_value('AllocNodes'))
        self.time_limit = convert_time(line_reader.get_value('Timelimit'))
        self.comment = self.__parse_str(
            line_reader.get_value('Comment'))

    @staticmethod
    def __parse_job_state(string):
        return JobState[string.split()[0]]

    @staticmethod
    def __convert_timestr_2_datetime(time_str):
        if time_str == 'Unknown':
            return None
        try:
            return parse(time_str).replace(tzinfo=tzlocal())
        except Exception:
            logger.warning('Fail to convert time str to datetime')
            return None

    @staticmethod
    def __convert_tres_2_dict(tres_str):
        gpu_dict = defaultdict(int)
        gpu_count = 0
        for tres in tres_str.split(','):
            # AllocTRES=cpu=4,gres/gpu=1,gres/gpu:2g.10gb=1
            t = tres.strip().split('=')
            if len(t) == 2 and t[0].strip() == 'gres/gpu':
                gpu_count = round(float(t[1]), 2)
            elif len(t) == 2 and t[0].startswith('gres/gpu'):
                gpu_type = t[0].lstrip('gres/gpu:')
                gpu_dict[gpu_type] += round(float(t[1]), 2)

        if len(gpu_dict):
            return {'gpu': gpu_dict}
        else:
            return {'gpu': {"no_type": gpu_count}}

    @staticmethod
    def __parse_str(string):
        return None if string == 'Unknown' else string

    @staticmethod
    def __parse_integer(string):
        return None if string == 'Unknown' or not string else int(string)

    def is_job_terminated(self):
        return self.term_time is not None

    def is_sub_event(self):
        try:
            if self.job_id.index('.') >= 0:
                return True
        except ValueError:
            logger.info('This is job id %s main event.', self.job_id)
            return False

    def merge_sub_event(self, sub_event):
        try:
            # Check the relation
            if sub_event.job_id.index(self.job_id + '.') == 0:
                step_mem = calculate_step_mem(
                    step_mem=sub_event.avg_mem,
                    step_ntasks=sub_event.ntasks if sub_event.ntasks else 0,
                    step_elapsed=sub_event.run_time,
                    job_elapsed_time=self.run_time
                )
                if step_mem >= 0:
                    self.avg_mem += step_mem
        except ValueError:
            logger.info(
                "Sub event jobid %s does not match main event jobid %s",
                sub_event.job_id, self.job_id
            )

    def get_acct_job(self, default_memory_usage_per_core=0):
        job = Job()
        if self.idx <= 0:
            scheduler_id = self.job_id
        else:
            scheduler_id = '{0}[{1}]'.format(self.job_id, self.idx)
        if self.submit_time is None:
            logger.error(
                "Acct job cannot get valid submit time. Jobid: %s",
                scheduler_id
            )
            return None
        job.identity = JobIdentity(
            scheduler_id=scheduler_id,
            submit_time=self.submit_time
        )
        job.name = self.job_name
        job.queue_name = self.queue
        job.submitter_username = self.user_name
        job.submit_time = self.submit_time
        job.start_time = self.start_time
        job.end_time = self.term_time
        job.runtime = self.run_time
        job.exit_code = self.exit_code
        job.state = self.state
        job.workspace_path = self.workdir
        job.comment = self.comment
        job.time_limit = self.time_limit

        if self.avg_mem < 0:
            # The unit of defaultMemoryUsagePerCore is MB
            memory = round(
                self.num_processors * default_memory_usage_per_core, 2
            )
        else:
            # The unit is MB
            memory = round(self.avg_mem / 1024, 2)

        average_cpu_num = 0
        average_gres = {}
        if self.node_list and self.nodes_count:
            average_cpu_num = int(self.num_processors / self.nodes_count)
            for key, value in self.gres_hosts.items():
                average_gres[key] = {
                    k: round(v / self.nodes_count, 2) for k, v in value.items()
                }

        if self.node_list and self.node_list.lower() != 'none assigned':
            hosts = expand_host_list(self.node_list)
            job.running_list = get_job_running_list(
                hosts, average_cpu_num, memory, average_gres
            )

        job.resource_list = get_job_resource_list(
            self.nodes_count, average_cpu_num, memory, average_gres
        )

        return job


def query_events_by_time(start_timestamp, end_timestamp):  # noqa: C901
    events = []
    time_range = 3600 * 24
    from datetime import datetime
    try:
        start = datetime.fromtimestamp(
            start_timestamp - time_range
        ).strftime(sacct_time_format)
        end = datetime.fromtimestamp(
            end_timestamp + time_range
        ).strftime(sacct_time_format)

        cmd = [
            "sacct",
            "-S", start, "-E", end,
            "-P", "--delimiter", delimiter,
            "--noheader", "--format", ','.join(SLURM_SACCT_FIELDS)
        ]

        out = check_output(cmd)
        lines = out.decode().splitlines()

        line_num = 0
        for line in lines:
            line_num += 1

            try:
                line_reader = AcctLineReader(line)
                event = AcctEvent(line_reader)
                if event.is_job_terminated():
                    term_time = int(event.term_time.timestamp())
                    if start_timestamp <= term_time <= end_timestamp:
                        if event.is_sub_event():
                            for main_event in events:
                                main_event.merge_sub_event(event)
                        else:
                            events.insert(0, event)
                else:
                    logging.info(
                        "The job %s end time is unknown, "
                        "don't process the job.", event.job_id)
            except Exception:
                logger.warning('Line %s', line_num, exc_info=True)
    except Exception as e:
        logger.exception("slurm acct parser failed.")
        raise AcctException from e
    return events
