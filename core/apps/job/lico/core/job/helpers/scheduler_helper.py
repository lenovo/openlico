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

from django.conf import settings

from lico.scheduler.adapter.scheduler_factory import (
    create_job_identity, create_lsf_scheduler, create_pbs_scheduler,
    create_slurm_scheduler,
)


def get_scheduler(user):
    return create_scheduler(user)


def get_admin_scheduler():
    return create_scheduler()


def create_scheduler(user=None):
    username = user.username if user else 'root'

    scheduler_code = settings.LICO.SCHEDULER
    if scheduler_code == 'slurm':
        from lico.scheduler.adapter.slurm.slurm_config import (
            SchedulerConfig as SlurmConfig,
        )
        return create_slurm_scheduler(
            username,
            config=SlurmConfig(
                memory_retry_count=settings.JOB.SLURM.get(
                    'MEMORY_RETRY_COUNT', 1
                ),
                memory_retry_interval_second=settings.JOB.SLURM.get(
                    'MEMORY_RETRY_INTERVAL_SECOND', 0.5
                )
            )
        )
    if scheduler_code == 'pbs':
        from lico.scheduler.adapter.pbs.pbs_config import (
            SchedulerConfig as PbsConfig,
        )
        return create_pbs_scheduler(
            username,
            config=PbsConfig()
        )
    if scheduler_code == 'lsf':
        from lico.scheduler.adapter.lsf.lsf_config import (
            SchedulerConfig as LsfConfig,
        )
        return create_lsf_scheduler(
            username,
            config=LsfConfig(
                acct_file_path=settings.JOB.LSF.get(
                    'ACCT_FILE_PATH', ""
                )
            )
        )
    return None


def parse_job_identity(identity_str):
    scheduler_code = settings.LICO.SCHEDULER
    return create_job_identity(scheduler_code, identity_str)
