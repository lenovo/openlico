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


class JobOperateState(Enum):
    CREATING = 'creating'
    CREATE_FAIL = 'create_fail'
    CREATED = 'created'
    CANCELLING = 'cancelling'
    CANCELLED = 'cancelled'


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
