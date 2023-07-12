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

from enum import Enum

from lico.scheduler.base.job.job_state import JobState as SchedulerJobState


class JobState(Enum):
    COMPLETED = 'C'
    # CANCELLED = 'CA'
    QUEUING = 'Q'
    RUNNING = 'R'
    HOLD = 'H'
    SUSPENDED = 'S'
    UNKNOWN = 'UN'

    @classmethod
    def get_state_value(cls, state):
        if isinstance(state, list):
            return [s.value for s in state]
        else:
            return state.value

    @classmethod
    def get_final_states(cls):
        return [
            JobState.COMPLETED,
            # JobState.CANCELLED
        ]

    @classmethod
    def get_final_state_values(cls):
        return cls.get_state_value(cls.get_final_states())

    @classmethod
    def get_waiting_states(cls):
        return [
            JobState.QUEUING,
            JobState.RUNNING,
            JobState.HOLD,
            JobState.SUSPENDED,
        ]

    @classmethod
    def get_waiting_state_values(cls):
        return cls.get_state_value(cls.get_waiting_states())

    @classmethod
    def get_allocating_states(cls):
        return [
            JobState.QUEUING,
            JobState.HOLD,
            JobState.SUSPENDED,
        ]

    @classmethod
    def get_allocating_state_values(cls):
        return cls.get_state_value(cls.get_allocating_states())

    @classmethod
    def from_scheduler_job_state(cls, scheduler_job_state):
        switch = {
            SchedulerJobState.BOOT_FAIL: JobState.COMPLETED,
            SchedulerJobState.CANCELLED: JobState.COMPLETED,
            SchedulerJobState.COMPLETED: JobState.COMPLETED,
            SchedulerJobState.CONFIGURING: JobState.QUEUING,
            SchedulerJobState.COMPLETING: JobState.RUNNING,
            SchedulerJobState.DEADLINE: JobState.COMPLETED,
            SchedulerJobState.FAILED: JobState.COMPLETED,
            SchedulerJobState.NODE_FAIL: JobState.COMPLETED,
            SchedulerJobState.OUT_OF_MEMORY: JobState.COMPLETED,
            SchedulerJobState.PENDING: JobState.QUEUING,
            SchedulerJobState.PREEMPTED: JobState.QUEUING,
            SchedulerJobState.RUNNING: JobState.RUNNING,
            SchedulerJobState.RESV_DEL_HOLD: JobState.HOLD,
            SchedulerJobState.REQUEUE_FED: JobState.QUEUING,
            SchedulerJobState.REQUEUE_HOLD: JobState.QUEUING,
            SchedulerJobState.HOLD: JobState.HOLD,
            SchedulerJobState.REQUEUED: JobState.QUEUING,
            SchedulerJobState.RESIZING: JobState.RUNNING,
            SchedulerJobState.REVOKED: JobState.COMPLETED,
            SchedulerJobState.SIGNALING: JobState.RUNNING,
            SchedulerJobState.SPECIAL_EXIT: JobState.QUEUING,
            SchedulerJobState.STAGE_OUT: JobState.RUNNING,
            SchedulerJobState.STOPPED: JobState.RUNNING,
            SchedulerJobState.SUSPENDED: JobState.SUSPENDED,
            SchedulerJobState.TIMEOUT: JobState.COMPLETED,
            SchedulerJobState.UNKNOWN: JobState.UNKNOWN,
        }
        try:
            return switch[scheduler_job_state]
        except KeyError:
            return JobState.UNKNOWN
