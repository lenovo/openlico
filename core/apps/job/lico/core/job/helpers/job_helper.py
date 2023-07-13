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
from django.db.transaction import atomic

from lico.scheduler.base.job.job_state import JobState as SchedulerJobState
from lico.scheduler.base.tres.trackable_resource_type import (
    TrackableResourceType,
)

from ..base.job_operate_state import JobOperateState
from ..base.job_state import JobState
from ..models import JobRunning
from .utils import _tres_list_to_dict, _tres_to_str

logger = logging.getLogger(__name__)


def job_need_recycle(current_state, next_state):
    if current_state in JobState.get_waiting_state_values()\
            and next_state in JobState.get_final_state_values():
        return True
    else:
        return False


def job_changed(job_pair):
    job = job_pair.job
    scheduler_job = job_pair.scheduler_job
    sche_q = scheduler_job.queue_name if scheduler_job.queue_name else ''

    conditions = [
        job.scheduler_state != scheduler_job.state.value,
        job.queue != sche_q,
        job.start_time != scheduler_job.start_time,
        job.end_time != scheduler_job.end_time,
        job.standard_output_file != scheduler_job.standard_output_filename,
        job.error_output_file != scheduler_job.error_output_filename,
        scheduler_job.runtime - job.runtime >
        settings.JOB.JOB_SYNC_RUNTIME_INTERVAL,
        job.priority != scheduler_job.priority,
    ]

    if any(conditions):
        return True
    else:
        # If scheduler stopped time exceed SCHEDULER_MAINTAINABLE_TIME,
        # will set job state to C.
        # When scheduler started, job still in queuing/running state,
        # need update job state revert to real state
        return job.state != \
               JobState.from_scheduler_job_state(scheduler_job.state).value


def update_job_by_scheduler_job(job, scheduler_job):  # noqa: C901
    logger.debug(" === update_job_by_scheduler_job === %s" % scheduler_job)
    update_fields = [
        'scheduler_id', 'identity_str', 'scheduler_state', 'state',
        'update_time'
    ]

    last_job_state = job.state
    append = update_fields.append

    job.scheduler_id = scheduler_job.identity.get_display()
    job.identity_str = scheduler_job.identity.to_string()
    job.scheduler_state = scheduler_job.state.value
    job.state = JobState.from_scheduler_job_state(scheduler_job.state).value

    if job.state not in JobState.get_final_state_values() or \
            job.start_time is None or \
            (scheduler_job.end_time and
             job.start_time > scheduler_job.end_time):
        job.start_time = scheduler_job.start_time
        append('start_time')

    if last_job_state not in JobState.get_final_state_values() or \
            job.end_time is None or \
            (scheduler_job.end_time and
             job.end_time > scheduler_job.end_time):
        job.end_time = scheduler_job.end_time
        append('end_time')

    if scheduler_job.runtime != -1:
        job.runtime = scheduler_job.runtime
        append('runtime')
    elif job.start_time and job.end_time:
        job.runtime = int((job.end_time - job.start_time).total_seconds())
        append('runtime')

    if scheduler_job.submitter_username:
        job.submitter = scheduler_job.submitter_username
        append('submitter')
    if scheduler_job.queue_name:
        job.queue = scheduler_job.queue_name
        append('queue')
    if scheduler_job.submit_time:
        job.submit_time = scheduler_job.submit_time
        append('submit_time')
    if scheduler_job.job_filename:
        job.job_file = scheduler_job.job_filename
        append('job_file')
    if scheduler_job.workspace_path:
        job.workspace = scheduler_job.workspace_path
        append('workspace')
    if scheduler_job.standard_output_filename:
        job.standard_output_file = scheduler_job.standard_output_filename
        append('standard_output_file')
    if scheduler_job.error_output_filename:
        job.error_output_file = scheduler_job.error_output_filename
        append('error_output_file')
    if scheduler_job.comment:
        job.comment = scheduler_job.comment
        append('comment')
    if scheduler_job.exit_code is not None:
        job.exit_code = scheduler_job.exit_code
        append('exit_code')
    if scheduler_job.priority:
        job.priority = scheduler_job.priority
        append('priority')

    # job.raw_info = ''
    # job.reason = ''

    tres_str_list = [_tres_to_str(res) for res in scheduler_job.resource_list]
    if tres_str_list:
        if last_job_state in JobState.get_allocating_state_values():
            job.tres = ','.join(tres_str_list)
        else:
            job.tres = _get_updated_tres_str(
                job_tres_list=job.tres.split(','),
                scheduler_tres_list=tres_str_list
            )
        append('tres')

    if scheduler_job.state == SchedulerJobState.CANCELLED:
        job.operate_state = JobOperateState.CANCELLED.value
        append('operate_state')

    _update_job_running(job, scheduler_job.running_list)
    return update_fields


def _scheduler_dt_to_job_dt(sched_datetime, job_datetime):
    return sched_datetime if sched_datetime is not None else job_datetime


def _update_job_running(job, scheduler_job_running_list, sync_history=False):
    with atomic():
        if job.start_time:
            JobRunning.objects.filter(
                job=job,
            ).exclude(allocate_time=job.start_time).delete()
        for running in scheduler_job_running_list:
            per_host_tres_str_list = []
            for res in running.per_host_resource_list:
                if res.type == TrackableResourceType.NODES:
                    continue
                per_host_tres_str_list.append(_tres_to_str(res))
            running.hosts.sort()

            if sync_history:
                JobRunning.objects.update_or_create(
                    job=job,
                    hosts=",".join(running.hosts),
                    defaults={
                        "per_host_tres": ','.join(per_host_tres_str_list),
                        "allocate_time": job.start_time
                    }
                )
            else:
                job_running_obj = JobRunning.objects.filter(
                    job=job,
                    hosts=",".join(running.hosts)
                )

                if job_running_obj.exists():
                    job_running_tres = job_running_obj[0].per_host_tres
                    job_running_obj.update(per_host_tres=_get_updated_tres_str(
                        job_tres_list=job_running_tres.split(','),
                        scheduler_tres_list=per_host_tres_str_list
                    ))
                else:
                    JobRunning.objects.create(
                        job=job,
                        hosts=",".join(running.hosts),
                        per_host_tres=','.join(per_host_tres_str_list),
                        allocate_time=job.start_time
                    )


def update_history_job_by_scheduler_job(query_job, scheduler_job):
    query_job.start_time = _get_field_value(
        query_job.start_time, scheduler_job.start_time
    )
    query_job.end_time = _get_field_value(
        query_job.end_time, scheduler_job.end_time
    )
    query_job.runtime = _get_field_value(
        query_job.runtime, scheduler_job.runtime
    )

    # update job.state, job.scheduler_state, job.operate_state
    query_job.scheduler_state = scheduler_job.state.value
    query_job.state = \
        JobState.from_scheduler_job_state(scheduler_job.state).value
    if scheduler_job.state == SchedulerJobState.CANCELLED:
        query_job.operate_state = JobOperateState.CANCELLED.value

    tres_str_list = [_tres_to_str(res) for res in scheduler_job.resource_list]
    if tres_str_list:
        query_job.tres = ','.join(tres_str_list)

    _update_job_running(
        query_job, scheduler_job.running_list,
        sync_history=True)

    query_job.save()


def _get_field_value(db_val, scheduler_val):
    if scheduler_val and scheduler_val != db_val:
        return scheduler_val
    else:
        return db_val


def _get_updated_tres_str(job_tres_list, scheduler_tres_list):
    # tres_list sample: ["M:2.13", "N:1", "C:4.0", "G/gpu:1.0"]

    job_tres_dict = _tres_list_to_dict(job_tres_list)
    scheduler_tres_dict = _tres_list_to_dict(scheduler_tres_list)

    job_tres_dict.update(scheduler_tres_dict)

    result_list = [f"{k}:{v}" for k, v in job_tres_dict.items()]
    return ','.join(result_list)
