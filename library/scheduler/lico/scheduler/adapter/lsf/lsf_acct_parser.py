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
import os
from datetime import datetime
from typing import Optional

from dateutil.tz import tz

from lico.scheduler.adapter.lsf.lsf_job_identity import JobIdentity
from lico.scheduler.base.exception.job_exception import (
    AcctInvalidValueException, AcctInvalidVersionException,
    AcctNoFieldException,
)
from lico.scheduler.base.job.job_running import JobRunning
from lico.scheduler.base.job.job_state import JobState
from lico.scheduler.base.scheduler import Job
from lico.scheduler.base.tres.trackable_resource import TrackableResource
from lico.scheduler.base.tres.trackable_resource_type import (
    TrackableResourceType,
)

logger = logging.getLogger(__name__)

SUPPORT_LSF_VERSION = '10.1'


class LSBAcctLineReader(object):
    def __init__(self, line):
        self.line = line
        self.offset = 0

    def goto_begin(self):
        self.offset = 0

    def read_next_field(self):
        # Check the end of line
        if self.offset >= len(self.line) or self.line[self.offset] \
                == '\r' or self.line[self.offset] == '\n':
            return None
        # If current character is quote, that means this is string field.
        if self.line[self.offset] == '"':
            look_for = '" '
            start_look_for_offset = self.offset
            try:
                while True:
                    pos = self.line.index(look_for, start_look_for_offset+1)
                    if self.line[pos-1] == '"' and self.line[pos-2] != '"' \
                            and pos > (self.offset + 1):
                        # Need escape, continue look for ends
                        start_look_for_offset = pos + 1
                    elif pos > 2 and self.line[pos-3:pos+1] == '""""':
                        start_look_for_offset = pos + 1
                    else:
                        # Real string field ends
                        raw_val = self.line[self.offset:pos+1]
                        self.offset = pos + len(look_for)
                        break
            except ValueError:
                return None
        else:
            look_for = ' '
            try:
                # Look for the next quote
                pos = self.line.index(look_for, self.offset+1)
                raw_val = self.line[self.offset:pos+1]
                # Skip one space
                self.offset = pos + len(look_for)
            except ValueError:
                return None
        return raw_val

    def skip_fields(self, fields):
        for field in fields:
            if isinstance(field, tuple):
                self.__skip_dynamic_field(field)
            else:
                self.__skip_fixed_field(field)

    def __skip_fixed_field(self, field_name):
        raw_val = self.read_next_field()
        if raw_val is None:
            logger.exception('Can not find field "%s"' % field_name)
            raise AcctNoFieldException(field_name)

    def __skip_dynamic_field(self, field_name_arr):
        num_field_name = field_name_arr[0]
        num_raw_val = self.read_next_field()
        if num_raw_val is None:
            logger.exception('Can not find field "%s"' % num_field_name)
            raise AcctNoFieldException(num_field_name)
        try:
            num_val = int(num_raw_val)
        except ValueError:
            logger.exception('Field "%s" has an invalid value "%s"'
                             % (num_field_name, num_raw_val))
            raise AcctInvalidValueException(num_field_name, num_raw_val)
        for idx in range(num_val):
            for field_idx in range(len(field_name_arr)-1):
                field_name = '{0}.{1}.{2}'.format(
                    num_field_name,
                    idx,
                    field_name_arr[field_idx+1])
                self.__skip_fixed_field(field_name)


class LSBAcctEvent(object):
    def __init__(self, line_reader=None):
        self.line_reader = line_reader
        self.event_type = ''
        self.version = ''
        self.event_time = 0
        if self.line_reader is not None:
            # (field_name, field_type, skip_fields_before_parse)
            parse_policies = [
                ('event_type', 'string', []),
                ('version', 'string', []),
                ('event_time', 'int', [])
            ]
            # Base information must be at the begin of the line
            self.line_reader.goto_begin()
            self.batch_parse_fields(parse_policies)
            # Check version
            if not self.version.startswith(SUPPORT_LSF_VERSION):
                logger.exception('Invalid version "%s", only support "%s"'
                                 % (self.version, SUPPORT_LSF_VERSION))
                raise AcctInvalidVersionException(
                    self.version, SUPPORT_LSF_VERSION)

    def batch_parse_fields(self, parse_policies):  # noqa:C901
        for policy in parse_policies:
            field_name = policy[0]
            field_type = policy[1]
            skip_fields_before_parse = policy[2]
            # Skip fields
            self.line_reader.skip_fields(skip_fields_before_parse)
            # Read next field
            field_raw_val = self.line_reader.read_next_field()
            # read second field value in tuple type
            sec_field_name = ''
            sec_field_val = []

            # Whether reading is success
            if field_raw_val is None:
                logger.exception('Can not find field "%s"' % field_name)
                raise AcctNoFieldException(field_name)
            # Parse field value according type
            if field_type == 'int':
                try:
                    field_val = int(field_raw_val)
                except ValueError:
                    logger.exception('Field "%s" has an invalid value "%s"'
                                     % (field_name, field_raw_val))
                    raise AcctInvalidValueException(
                        field_name, field_raw_val)
            elif field_type == 'float':
                try:
                    field_val = float(field_raw_val)
                except ValueError:
                    logger.exception('Field "%s" has an invalid value "%s"'
                                     % (field_name, field_raw_val))
                    raise AcctInvalidValueException(
                        field_name, field_raw_val)
            elif field_type == 'string':
                if len(field_raw_val) >= 2 and field_raw_val[0] \
                        == '"' and field_raw_val[-1] == '"':
                    field_val = field_raw_val[1:-1]
                else:
                    logger.exception('Field "%s" has an invalid value "%s"'
                                     % (field_name, field_raw_val))
                    raise AcctInvalidValueException(
                        field_name, field_raw_val)
            elif field_type == 'tuple':
                field_name_arr = field_name
                try:
                    field_val = int(field_raw_val)
                except ValueError:
                    raise
                for idx in range(field_val):
                    for field_idx in range(len(field_name_arr) - 1):
                        sec_raw_val = self.line_reader.read_next_field()
                        if len(sec_raw_val) >= 2 and sec_raw_val[0] \
                                == '"' and sec_raw_val[-1] == '"':
                            sec_field_val.append(sec_raw_val[1:-1])
                        else:
                            logger.exception(
                                'Field "%s" has an invalid value "%s"'
                                % (field_name, field_raw_val)
                            )
                            raise AcctInvalidValueException(
                                field_name_arr[1], sec_field_val[0])
                field_name = field_name_arr[0]
                sec_field_name = field_name_arr[1]
            else:
                # Unreachable
                field_val = None
            setattr(self, field_name, field_val)
            setattr(self, sec_field_name, ','.join(set(sec_field_val)))


class JobFinishEvent(LSBAcctEvent):
    def __init__(self, line_reader=None):
        super(JobFinishEvent, self).__init__(line_reader)
        self.job_id = 0
        self.num_processors = 0
        self.submit_time = 0
        self.term_time = 0
        self.start_time = 0
        self.user_name = ''
        self.queue = ''
        self.job_name = ''
        self.idx = 0
        self.max_rmem = 0
        self.max_rswap = 0
        self.avg_mem = 0
        self.num_alloc_slots = 0
        self.num_exhosts = 0
        self.exec_hosts = ''
        self.working_dir = ''
        self.out_file = ''
        self.err_file = ''
        if self.line_reader is not None:
            # (field_name, field_type, skip_fields_before_parse)
            parse_policies = [
                ('job_id', 'int', []),
                ('num_processors', 'int', ['userId', 'options']),
                ('submit_time', 'int', []),
                ('term_time', 'int', ['beginTime']),
                ('start_time', 'int', []),
                ('user_name', 'string', []),
                ('queue', 'string', []),
                ('working_dir', 'string', ['resReq', 'dependCond',
                                           'preExecCmd', 'fromHost']),
                ('out_file', 'string', ['inFile']),
                ('err_file', 'string', []),
                (('num_asked_hosts', 'askedHosts'),
                 'tuple', ['jobFile']),
                (('num_exhosts', 'exec_hosts'), 'tuple', []),
                ('job_name', 'string', ['jStatus', 'hostFactor']),
                ('idx', 'int', ['command', 'ru_utime', 'ru_stime', 'ru_maxrss',
                                'ru_ixrss', 'ru_ismrss', 'ru_idrss',
                                'ru_isrss', 'ru_minflt', 'ru_majflt',
                                'ru_nswap', 'ru_inblock', 'ru_oublock',
                                'ru_ioch', 'ru_msgsnd', 'ru_msgrcv',
                                'ru_nsignals', 'ru_nvcsw', 'ru_nivcsw',
                                'ru_exutime', 'mailUser', 'projectName',
                                'exitStatus', 'maxNumProcessors',
                                'loginShell', 'timeEvent']),
                ('max_rmem', 'int', []),
                ('max_rswap', 'int', []),
                ('avg_mem', 'int', ['inFileSpool', 'commandSpool', 'rsvId',
                                    'sla', 'exceptMask', 'additionalInfo',
                                    'exitInfo', 'warningAction',
                                    'warningTimePeriod', 'chargedSAAP',
                                    'licenseProject', 'app', 'postExecCmd',
                                    'runtimeEstimation', 'jobGroupName',
                                    'requeueEvalues', 'options2',
                                    'resizeNotifyCmd', 'lastResizeTime',
                                    'rsvId', 'jobDescription',
                                    ('submitExtNum', 'key', 'value'),
                                    ('numHostRusage', 'hostname',
                                     'mem', 'swap', 'utime',
                                     'stime'),
                                    'options3', 'runLimit']),
                ('run_time', 'int', ['effectiveResReq', 'srcCluster',
                                     'srcJobId', 'dstCluster', 'dstJobId',
                                     'forwardTime', 'flow_id', 'acJobWaitTime',
                                     'totalProvisionTime', 'outdir']),
                ('num_alloc_slots', 'int', ['subcwd', ('num_network',
                                            'networkID', 'num_window'),
                                            'affinity', 'serial_job_energy',
                                            'cpi', 'gips', 'gbs', 'gflops'])
            ]
            self.batch_parse_fields(parse_policies)

    def convert_timestamp_2_datetime(
            self, timestamp: int
    ) -> Optional[datetime]:
        try:
            date_time = datetime.fromtimestamp(timestamp)
            timezone = tz.tzlocal()
            datetime_tz = date_time.replace(tzinfo=timezone)

            return datetime_tz
        except Exception:
            logger.warning('Fail to convert timestamp to datetime')
            return None

    def parse_trackable_resource(self, default_memory_usage_per_core):
        resource_list = []
        job_running = JobRunning()

        cpuscount = max(self.num_processors, self.num_alloc_slots)
        gpuscount = 0
        nodescount = len(self.exec_hosts.split(","))

        if self.avg_mem < 0:
            # The unit of defaultMemoryUsagePerCore is MB
            memory = round(
                self.num_processors * default_memory_usage_per_core, 2
            )
        else:
            # The unit is MB
            memory = round(self.avg_mem / 1024, 2)

        if nodescount:
            resource_list.append(TrackableResource(
                type=TrackableResourceType.NODES,
                code=None, count=nodescount
            ))
            job_running.hosts = self.exec_hosts.split(",")
            if cpuscount:
                job_running.per_host_resource_list.append(
                    TrackableResource(
                        type=TrackableResourceType.CORES,
                        code=None,
                        count=cpuscount / nodescount
                    ))
                resource_list.append(TrackableResource(
                    type=TrackableResourceType.CORES,
                    code=None, count=cpuscount
                ))
            if gpuscount:
                job_running.per_host_resource_list.append(TrackableResource(
                    type=TrackableResourceType.GRES,
                    code="gpu",
                    count=gpuscount / nodescount
                ))
                resource_list.append(TrackableResource(
                    type=TrackableResourceType.GRES,
                    code="gpu", count=gpuscount
                ))
            if memory:
                job_running.per_host_resource_list.append(TrackableResource(
                    type=TrackableResourceType.MEMORY,
                    code=None,
                    count=memory / nodescount
                ))
                resource_list.append(TrackableResource(
                    type=TrackableResourceType.MEMORY,
                    code=None, count=memory
                ))

        return [job_running], resource_list

    def get_acct_job(self, default_memory_usage_per_core=0):
        job = Job()

        job.name = self.job_name
        job.submit_time = self.convert_timestamp_2_datetime(self.submit_time)
        if job.submit_time is None:
            logger.error(
                "Acct job cannot get valid submit time. Jobid: %s",
                str(self.job_id)
            )
            return None
        start_time = self.start_time \
            if self.start_time > 0 else self.submit_time
        job.start_time = self.convert_timestamp_2_datetime(start_time)
        end_time = self.term_time \
            if self.term_time > 0 else self.event_time
        job.end_time = self.convert_timestamp_2_datetime(end_time)
        job.submitter_username = self.user_name
        job.state = JobState.COMPLETED
        job.running_list, job.resource_list = \
            self.parse_trackable_resource(default_memory_usage_per_core)
        job.workspace_path = self.working_dir
        job.job_filename = None
        job.standard_output_filename = \
            os.path.join(self.working_dir, self.out_file)
        job.error_output_filename = \
            os.path.join(self.working_dir, self.err_file)
        job.exit_code = None
        job.queue_name = self.queue
        job.runtime = int((job.end_time - job.start_time).total_seconds())
        job.time_limit = None

        if self.idx <= 0:
            job.identity = JobIdentity(
                scheduler_id=str(self.job_id),
                submit_time=job.submit_time
            )
        else:
            job.identity = JobIdentity(
                scheduler_id='{0}[{1}]'.format(self.job_id, self.idx),
                submit_time=job.submit_time
            )

        return job


def query_events_by_time(filename, start_time, end_time):
    result = []
    line_cache = []
    max_line_cache_size = 5000
    with open(filename, 'r') as f:
        line_num = 0
        begin_line_num_in_cache = 0
        while True:
            line_num += 1
            line = f.readline()
            if line:
                if len(line_cache) < max_line_cache_size:
                    line_cache.append(line)
                else:
                    # Proccess line cache
                    line_cache.append(line)
                    events = __parse_events_from_lines(
                        line_cache, begin_line_num_in_cache,
                        start_time, end_time)
                    result.extend(events)
                    line_cache = []
                    begin_line_num_in_cache = (line_num + 1)
            else:
                break
        # Process the left line cache
        events = __parse_events_from_lines(
            line_cache, begin_line_num_in_cache,
            start_time, end_time)
        result.extend(events)
    return result


def __parse_events_from_lines(lines, begin_line_num, start_time, end_time):
    # Empty lines
    if len(lines) <= 0:
        return []
    # Check the lines are in time range
    begin_event = LSBAcctEvent(LSBAcctLineReader(lines[0]))
    end_event = LSBAcctEvent(LSBAcctLineReader(lines[-1]))
    if begin_event.event_time > end_time or end_event.event_time < start_time:
        return []
    # Parse lines one by one, a litte slow...
    events = []
    line_offset = 0
    for line in lines:
        line_num = begin_line_num + line_offset
        try:
            line_reader = LSBAcctLineReader(line)
            base_event = LSBAcctEvent(line_reader)
            if start_time <= base_event.event_time <= end_time:
                if base_event.event_type == 'JOB_FINISH':
                    event = JobFinishEvent(line_reader)
                    events.append(event)
        except Exception:
            logger.warning('Line %s', line_num, exc_info=True)
        line_offset += 1
    return events
