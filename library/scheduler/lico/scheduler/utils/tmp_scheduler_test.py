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

#######################################################
#                   ONLY FOR TESTING                  #
#           WILL BE REMOVED AFTER CODE FINISHED       #
#######################################################

from lico.scheduler.adapter.scheduler_factory import create_slurm_scheduler
from lico.scheduler.adapter.slurm.slurm_config import (
    SchedulerConfig as SlurmConfig,
)


def test_slurm_submit():
    slurm_config = SlurmConfig(
        tracking_gres_list=["gpu"]
    )
    sched = create_slurm_scheduler(
        operator_username="hpcadmin",
        config=slurm_config
    )

    sched.submit_job(job_content="some content")


test_slurm_submit()
