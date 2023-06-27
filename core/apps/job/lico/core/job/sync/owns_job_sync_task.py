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

from lico.scheduler.base.exception.job_exception import QueryJobFailedException

from ..base.job_state import JobState
from ..helpers.scheduler_helper import get_scheduler, parse_job_identity
from ..models import Job
from .job_sync_task import JobSyncTask
from .sync_job_pair import SyncJobPair

logger = logging.getLogger(__name__)


class OwnsJobSyncTask(JobSyncTask):
    def __init__(self):
        self._scheduler_dict = dict()

    def _get_sync_job_pair_list(self, query_memory=False):
        job_pair_list = []
        # Query all waiting jobs from database
        logger.debug(
            "Waiting States: {}".format(JobState.get_waiting_state_values())
        )
        waiting_jobs = Job.objects.filter(
            state__in=JobState.get_waiting_state_values()
        )
        logger.debug(
            "Waiting Jobs: {}".format(waiting_jobs)
        )
        for job in waiting_jobs:
            if job.identity_str:
                scheduler = self.__get_scheduler(job.submitter)
                # If can't get user's scheduler,
                # the job will be hold on current status.
                # Need consider this due to lico issue,
                # the job can recovery after issue fixed.
                if scheduler:
                    identity = parse_job_identity(job.identity_str)
                    try:
                        scheduler_job = scheduler.query_job(identity)
                    except QueryJobFailedException:
                        scheduler_job = None
                    job_pair = SyncJobPair(
                        job=job,
                        scheduler_job=scheduler_job
                    )
                else:
                    continue
            else:
                job_pair = SyncJobPair(
                    job=job,
                    scheduler_job=None
                )
            job_pair_list.append(job_pair)
        return job_pair_list

    def __get_scheduler(self, username):
        if username not in self._scheduler_dict:
            from lico.client.contrib.exception import Unauthorized
            from lico.core.contrib.client import Client
            client = Client().auth_client()
            try:
                user = client.get_user_info(username=username)
                scheduler = get_scheduler(user)
            except Unauthorized:
                logger.warning("Unauthorized user: {}".format(username))
                scheduler = None
            if scheduler is None:
                logger.warning(
                    "Create scheduler failed for user: {}".format(username)
                )
            self._scheduler_dict[username] = scheduler
        return self._scheduler_dict[username]

    def _recycle_resources(self, job):
        scheduler = self.__get_scheduler(job.submitter)
        if scheduler:
            job_identity = parse_job_identity(job.identity_str)
            scheduler.recycle_resources(job_identity)
