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
import time
from abc import ABCMeta, abstractmethod

from django.conf import settings
from django.utils.timezone import now

from ..base.job_operate_state import JobOperateState
from ..base.job_state import JobState
from ..helpers.job_helper import (
    job_changed, job_need_recycle, update_job_by_scheduler_job,
)
from ..models import Job

logger = logging.getLogger(__name__)
JOB_FINAL_STATES = []

query_memory_recorder = time.time()


class JobSyncTask(metaclass=ABCMeta):
    # for jobs cannot be queried from scheduler
    missing_jobs_cache = {}

    def sync_job(self, ignore_job_identity_list=None):  # noqa: C901
        query_memory = False
        global query_memory_recorder
        current_time = time.time()
        if current_time - query_memory_recorder > \
                settings.JOB.JOB_SYNC_MEMORY_INTERVAL:
            query_memory = True
            query_memory_recorder = current_time
        job_pair_list = self._get_sync_job_pair_list(query_memory)
        logger.debug("Job pair list: {}".format(job_pair_list))
        for job_pair in job_pair_list:
            try:
                # Job that submit from console
                if job_pair.job is None:
                    job = Job.objects.create(
                        job_name=job_pair.scheduler_job.name[:128],
                        submitter=job_pair.scheduler_job.submitter_username,
                        job_content='',
                        operate_state=JobOperateState.CREATING.value,
                    )
                    update_job_by_scheduler_job(job, job_pair.scheduler_job)
                    job.operate_state = JobOperateState.CREATED.value
                    job.save()
                    self._on_job_changed(job, charge=True)
                    continue
                # Job that in creating
                if job_pair.scheduler_job is None:
                    update_fields = ['update_time']

                    # Creating job no identity
                    if job_pair.job.operate_state == \
                            JobOperateState.CREATING.value:
                        continue

                    # In case of scheduler stopped for reconfiguring or
                    # like. Sync task will not update job state or charge
                    # job until job’s missing time exceed
                    # SCHEDULER_MAINTAINABLE_TIME
                    current_time = now()
                    if job_pair.job.id not in self.missing_jobs_cache:
                        self.missing_jobs_cache[job_pair.job.id] = current_time
                        continue
                    else:
                        missing_time = self.missing_jobs_cache[job_pair.job.id]
                        if (current_time - missing_time).total_seconds() < \
                                settings.JOB.SCHEDULER_MAINTAINABLE_TIME:
                            continue
                        else:
                            del self.missing_jobs_cache[job_pair.job.id]

                    # Not creating job need be completed
                    # Because the cancelling RestAPI can update
                    # operate_state, so need reload object.
                    job_pair.job.refresh_from_db()
                    if job_pair.job.operate_state == \
                            JobOperateState.CANCELLING.value:
                        job_pair.job.operate_state = \
                            JobOperateState.CANCELLED.value
                        update_fields.append('operate_state')
                    job_pair.job.state = JobState.COMPLETED.value
                    update_fields.append('state')

                    # If lico lost connection with scheduler
                    # the jobs in final state cannot
                    # get end_time and runtime from scheduler any more.
                    # Therefore, patch the end_time and runtime to these jobs.
                    if job_pair.job.end_time is None:
                        start_time = job_pair.job.start_time
                        if start_time:
                            job_pair.job.end_time = max(
                                now(), job_pair.job.start_time
                            )
                            job_pair.job.runtime = int(
                                (job_pair.job.end_time -
                                 job_pair.job.start_time).total_seconds()
                            )
                        else:
                            job_pair.job.start_time = job_pair.job.submit_time
                            job_pair.job.end_time = job_pair.job.submit_time
                            job_pair.job.runtime = 0
                        update_fields.extend(
                            ['start_time', 'end_time', 'runtime']
                        )

                    job_pair.job.save(update_fields=update_fields)
                    self._on_job_changed(job_pair.job, charge=False)
                    # Don't need recycle job resource, because
                    # can't get job information from scheduler.
                    continue

                if job_pair.job.id in self.missing_jobs_cache:
                    del self.missing_jobs_cache[job_pair.job.id]

                # Update
                if (query_memory and job_pair.job.state not in
                        JobState.get_final_state_values()) or \
                        job_changed(job_pair):
                    # Only sync process can update state fields.
                    # So no need to reload.
                    current_state = job_pair.job.state
                    update_fields = update_job_by_scheduler_job(
                        job_pair.job,
                        job_pair.scheduler_job
                    )
                    job_pair.job.save(update_fields=update_fields)
                    next_state = job_pair.job.state
                    self._on_job_changed(job_pair.job, charge=True)
                    if job_need_recycle(current_state, next_state):
                        try:
                            self._recycle_resources(job_pair.job)
                        except Exception:
                            logger.exception(
                                "Recycle resource job: {}".format(job.id)
                            )
            except Exception:
                logger.exception("Sync job failed.")

    @abstractmethod
    def _get_sync_job_pair_list(self, query_memory=False):
        pass

    @abstractmethod
    def _recycle_resources(self, job):
        pass

    def _on_job_changed(self, job, charge):
        if charge:
            self._charge_job(job)
        self._notify_job(job)

    def _charge_job(self, job):
        if job.state not in JobState.get_final_state_values():
            return
        try:
            from lico.core.contrib.client import Client

            Client().accounting_client().notify_job_charge(job.as_dict())
        except Exception:
            logger.warning("Charge job failed. Job id: %s", job.id)

    def _notify_job(self, job):
        try:
            from lico.core.contrib.client import Client

            Client().template_client().notify_job(job.as_dict())
        except Exception:
            logger.warning("Notify job failed. Job id: %s", job.id)
