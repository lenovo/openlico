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

import attr

from lico.scheduler.base.job.job import Job as SchedulerJob

from ..models import Job


@attr.s(slots=True)
class SyncJobPair:
    job: Job = attr.ib(default=None)
    scheduler_job: SchedulerJob = attr.ib(default=None)
