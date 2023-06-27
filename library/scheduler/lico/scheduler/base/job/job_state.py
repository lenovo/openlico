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


class JobState(Enum):
    BOOT_FAIL = 'BF'
    CANCELLED = 'CA'
    COMPLETED = 'CD'
    CONFIGURING = 'CF'
    COMPLETING = 'CG'
    DEADLINE = 'DL'
    FAILED = 'F'
    NODE_FAIL = 'NF'
    OUT_OF_MEMORY = 'OOM'
    PENDING = 'PD'
    PREEMPTED = 'PR'
    RUNNING = 'R'
    RESV_DEL_HOLD = 'RD'
    REQUEUE_FED = 'RF'
    REQUEUE_HOLD = 'RH'
    REQUEUED = 'RQ'
    RESIZING = 'RS'
    REVOKED = 'RV'
    SIGNALING = 'SI'
    SPECIAL_EXIT = 'SE'
    STAGE_OUT = 'SO'
    STOPPED = 'ST'
    SUSPENDED = 'S'
    TIMEOUT = 'TO'
    UNKNOWN = 'UNKNOWN'

    @classmethod
    def get_final_state(cls):
        return [
            JobState.BOOT_FAIL,
            JobState.COMPLETED,
            JobState.CANCELLED,
            JobState.DEADLINE,
            JobState.FAILED,
            JobState.NODE_FAIL,
            JobState.OUT_OF_MEMORY,
            JobState.REVOKED,
            JobState.TIMEOUT
        ]

    @classmethod
    def get_running_state(cls):
        return [
            JobState.COMPLETING,
            JobState.RUNNING,
            JobState.RESIZING,
            JobState.SIGNALING,
            JobState.STAGE_OUT
        ]

    @classmethod
    def get_queuing_state(cls):
        return [
            JobState.CONFIGURING,
            JobState.PENDING,
            JobState.PREEMPTED,
            JobState.REQUEUE_FED,
            JobState.REQUEUE_HOLD,
            JobState.REQUEUED,
            JobState.SPECIAL_EXIT
        ]
