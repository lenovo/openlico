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
import os
import stat

from rest_framework.response import Response

from lico.core.contrib.authentication import RemoteJWTInternalAuthentication
from lico.core.contrib.eventlog import EventLog
from lico.core.contrib.views import InternalAPIView
from lico.scheduler.base.exception.job_exception import (
    SchedulerJobBaseException,
)

from ..base.job_comment import JobComment
from ..base.job_operate_state import JobOperateState
from ..base.job_state import JobState
from ..exceptions import JobFileNotExist, SubmitJobException
from ..helpers.csres_helper import get_csres_render
from ..helpers.fs_operator_helper import get_fs_operator
from ..helpers.job_helper import update_job_by_scheduler_job
from ..helpers.scheduler_helper import get_scheduler
from ..models import Job

logger = logging.getLogger(__name__)


class JobRerunView(InternalAPIView):
    authentication_classes = (
        RemoteJWTInternalAuthentication,
    )

    def post(self, request, pk):
        # Create scheduler
        submitter = request.user
        scheduler = get_scheduler(submitter)
        # Find origin job
        origin_job = Job.objects.filter(
            submitter=submitter.username,
            delete_flag=False
        ).get(id=pk)
        # Find origin job file
        job_file = origin_job.job_file
        if not os.path.isfile(job_file):
            logger.error('Job file not exist.')
            raise JobFileNotExist
        # Read job content
        job_content = origin_job.job_content
        # Init rerun job
        job = Job.objects.create(
            job_name=origin_job.job_name,
            submitter=submitter.username,
            job_file=job_file,
            workspace=origin_job.workspace,
            job_content=job_content,
            operate_state=JobOperateState.CREATING.value,
        )
        csres_render = get_csres_render()
        job_content = csres_render.render(job.id, job_content)
        # Save job file to user's workspace
        # By default, the job file will be generated under workspace path.
        job_filename = job_file
        self._save_job_file(job_filename, job_content, submitter)
        job.job_file = job_filename
        job.save()
        try:
            # Generate job comment
            job_comment = JobComment(job.id)
            # Scheduler adapter only can access local file.
            # If job file exist on local path, submit from file.
            job_identity = scheduler.submit_job_from_file(
                job_filename=job_file,
                job_name=origin_job.job_name,
                job_comment=job_comment.get_comment())
        except SchedulerJobBaseException as e:
            job.operate_state = JobOperateState.CREATE_FAIL.value
            job.state = JobState.COMPLETED.value
            job.save()
            logger.exception("Rerun job failed.")
            raise SubmitJobException(job_id=job.id) from e
        # Save job identity to database
        scheduler_job = scheduler.query_job(job_identity)
        update_job_by_scheduler_job(job, scheduler_job)
        if job.operate_state == JobOperateState.CREATING.value \
                or not job.operate_state:
            job.operate_state = JobOperateState.CREATED.value
        job.save()

        EventLog.opt_create(
            request.user.username, EventLog.job, EventLog.rerun,
            EventLog.make_list(job.id, origin_job.job_name)
        )
        # Make response
        return Response({'id': job.id})

    def _read_job_file(self, job_filename, user):
        fs_operator = get_fs_operator(user)
        job_content, _ = fs_operator.read_content(job_filename)
        return job_content

    def _save_job_file(self, job_filename, job_content, user):
        fs_operator = get_fs_operator(user)
        with fs_operator.open_file(job_filename, 'w') as f:
            f.file_handle.write(str(job_content))
        if user.uid and user.gid:
            fs_operator.chown(job_filename, user.uid, user.gid)
            fs_operator.chmod(job_filename, stat.S_IRUSR | stat.S_IWUSR)
