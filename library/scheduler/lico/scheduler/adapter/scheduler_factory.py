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

from importlib import import_module
from typing import Optional

from lico.scheduler.base.job.job_identity import IJobIdentity
from lico.scheduler.base.scheduler import IScheduler
from lico.scheduler.base.scheduler_config import BaseSchedulerConfig


def create_slurm_scheduler(
        operator_username,
        config: Optional[BaseSchedulerConfig] = None
) -> IScheduler:
    if config is None:
        from .slurm.slurm_config import SchedulerConfig
        config = SchedulerConfig()
    from .slurm.slurm_scheduler import Scheduler
    return Scheduler(operator_username, config)


def create_lsf_scheduler(
        operator_username,
        config: Optional[BaseSchedulerConfig] = None
) -> IScheduler:
    if config is None:
        from .lsf.lsf_config import SchedulerConfig
        config = SchedulerConfig()
    from .lsf.lsf_scheduler import Scheduler
    return Scheduler(operator_username, config)


def create_pbs_scheduler(
        operator_username,
        config: Optional[BaseSchedulerConfig] = None
) -> IScheduler:
    if config is None:
        from .pbs.pbs_config import SchedulerConfig
        config = SchedulerConfig()
    from .pbs.pbs_scheduler import Scheduler
    return Scheduler(operator_username, config)


def create_job_identity(scheduler_key, identity_str) -> IJobIdentity:
    module = import_module(
        f"lico.scheduler.adapter.{scheduler_key}.{scheduler_key}_job_identity"
    )
    return module.JobIdentity.from_string(identity_str)


# ======================= Scheduler Manager =======================

def create_slurm_manager(operator_username: str):
    from .slurm.slurm_scheduler_manager import SchedulerManager
    return SchedulerManager(operator_username)
