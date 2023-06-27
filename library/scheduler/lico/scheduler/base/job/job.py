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

from datetime import datetime
from typing import List

import attr

from ..tres.trackable_resource import TrackableResource
from .job_identity import IJobIdentity
from .job_running import JobRunning
from .job_state import JobState


@attr.s(slots=True)
class Job:
    identity: IJobIdentity = attr.ib(default=None)
    name: str = attr.ib(default=None)
    submit_time: datetime = attr.ib(default=None)
    start_time: datetime = attr.ib(default=None)
    end_time: datetime = attr.ib(default=None)
    submitter_username: str = attr.ib(default=None)
    state: JobState = attr.ib(default=None)
    resource_list: List[TrackableResource] = attr.ib(factory=list)
    running_list: List[JobRunning] = attr.ib(factory=list)
    workspace_path: str = attr.ib(default=None)
    job_filename: str = attr.ib(default=None)
    standard_output_filename: str = attr.ib(default=None)
    error_output_filename: str = attr.ib(default=None)
    exit_code: str = attr.ib(default=None)
    queue_name: str = attr.ib(default=None)
    runtime: int = attr.ib(default=0)        # "1-00:10:00" -> seconds
    time_limit: int = attr.ib(default=None)  # 0 means unlimited
    comment: str = attr.ib(default=None)
