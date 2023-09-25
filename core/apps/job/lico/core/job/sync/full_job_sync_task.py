# Copyright 2015-present Lenovo
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

from ..base.job_comment import JobComment
from ..base.job_state import JobState
from ..helpers.scheduler_helper import get_admin_scheduler, parse_job_identity
from ..models import Job
from .job_sync_task import JobSyncTask
from .sync_job_pair import SyncJobPair


class FullJobSyncTask(JobSyncTask):
    def __init__(self):
        self._scheduler = get_admin_scheduler()

    def _get_sync_job_pair_list(self, query_memory=False):
        job_pair_list = []
        # Query all waiting jobs from database
        waiting_jobs = Job.objects.filter(
            state__in=JobState.get_waiting_state_values()
        )
        for job in waiting_jobs:
            job_pair = SyncJobPair(
                job=job,
                scheduler_job=None
            )
            job_pair_list.append(job_pair)
        # Query recent jobs from scheduler
        recent_scheduler_jobs = self._scheduler.query_recent_jobs(query_memory)
        extend_job_pair_list = []
        for scheduler_job in recent_scheduler_jobs:
            found = False
            for job_pair in job_pair_list:
                if self.__is_same_job(job_pair.job, scheduler_job):
                    job_pair.scheduler_job = scheduler_job
                    found = True
                    break
            if found:
                continue
            # Handle not found job
            # job_state = JobState.from_scheduler_job_state(
            #   scheduler_job.state
            # )
            # if job_state in JobState.get_waiting_states():
            #     job_pair = SyncJobPair(
            #         job=None,
            #         scheduler_job=scheduler_job
            #     )
            # else:
            #     job_pair = SyncJobPair(
            #         job=self.__query_job_by_scheduler_job(
            #           scheduler_job
            #         ),
            #         scheduler_job=scheduler_job
            #     )
            # Not consider job state.
            # Because the job record created before you can see
            # the job from scheduler command line.
            # Once one job can be seen on scheduler,
            # it must be created in db and can find by comment-id.
            # If there is no job comment, and it submit from
            # lico-core-job, the duplicate job risk may exist.
            job_pair = SyncJobPair(
                job=self.__query_job_by_scheduler_job(scheduler_job),
                scheduler_job=scheduler_job
            )
            extend_job_pair_list.append(job_pair)
        return job_pair_list + extend_job_pair_list

    def __is_same_job(self, job, scheduler_job):
        job_id_in_comment = self.__parse_job_id_from_comment(
            scheduler_job.comment
        ) if scheduler_job.comment else -1
        return job.id == job_id_in_comment or \
            job.identity_str == scheduler_job.identity.to_string() or \
            job.identity_str == scheduler_job.identity.to_alternative_string()

    def __query_job_by_scheduler_job(self, scheduler_job):
        job_id_in_comment = self.__parse_job_id_from_comment(
            scheduler_job.comment
        ) if scheduler_job.comment else -1
        if job_id_in_comment > 0:
            try:
                return Job.objects.get(id=job_id_in_comment)
            except Job.DoesNotExist:
                pass
        job_identity_str = scheduler_job.identity.to_string()
        # If not found job by identity_str, it will return None.
        return Job.objects.filter(identity_str=job_identity_str).first()

    def __parse_job_id_from_comment(self, comment_str):
        job_comment = JobComment.from_comment(comment_str)
        if job_comment is None:
            return -1
        else:
            return job_comment.get_job_id()

    def _recycle_resources(self, job):
        job_identity = parse_job_identity(job.identity_str)
        self._scheduler.recycle_resources(job_identity)
