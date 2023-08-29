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

from django.conf import settings
from rest_framework.response import Response

from lico.core.contrib.authentication import RemoteJWTInternalAuthentication
from lico.core.contrib.eventlog import EventLog
from lico.core.contrib.schema import json_schema_validate
from lico.core.contrib.views import InternalAPIView
from lico.scheduler.base.exception.job_exception import (
    SchedulerJobBaseException,
)

from ..base.job_comment import JobComment
from ..base.job_operate_state import JobOperateState
from ..base.job_state import JobState
from ..exceptions import SubmitJobException
from ..helpers.csres_helper import get_csres_render
from ..helpers.fs_operator_helper import get_fs_operator
from ..helpers.job_helper import update_job_by_scheduler_job
from ..helpers.scheduler_helper import get_scheduler
from ..models import Job

logger = logging.getLogger(__name__)


class JobSubmitView(InternalAPIView):
    authentication_classes = (
        RemoteJWTInternalAuthentication,
    )

    @json_schema_validate({
        "type": "object",
        "properties": {
            "job_name": {
                "type": "string"
            }
        },
        "required": ["job_name"],
        "oneOf": [
            {
                "type": "object",
                "properties": {
                    "job_file": {
                        "type": "string"
                    }
                },
                "required": ["job_file"]
            },
            {
                "type": "object",
                "properties": {
                    "workspace": {
                        "type": "string"
                    },
                    "job_content": {
                        "type": "string"
                    }
                },
                "required": ["workspace", "job_content"]
            }
        ]
    })
    def post(self, request):
        # Create scheduler
        submitter = request.user
        scheduler = get_scheduler(submitter)
        # Init variables
        job_name = request.data['job_name'][:128]
        job_filename = request.data['job_file'] \
            if 'job_file' in request.data else ''
        workspace = request.data['workspace'] \
            if 'workspace' in request.data else ''
        job_content = request.data['job_content'] \
            if 'job_content' in request.data else ''
        # Save to database first, reasons:
        # 1. The cs-res need record the relationship with job.
        # 2. To rerun job, the cs-res need be re-allocate on running.
        job = Job.objects.create(
            job_name=job_name,
            submitter=submitter.username,
            job_file=job_filename,
            workspace=workspace,
            job_content=job_content,
            operate_state=JobOperateState.CREATING.value,
        )
        # If request contains "job_file",
        # that means submit job from file directly.
        if job_filename:
            job_content = self._read_job_file(job_filename, submitter)
            job.job_content = job_content
            job.save()
        # If request contains "workspace" and "job_content",
        # that means need render content and save to workspace.
        if workspace and job_content:
            # Cross Scheduler Resource allocate and render job content.
            csres_render = get_csres_render()
            job_content = csres_render.render(job.id, job_content)
            # Save job file to user's workspace
            # By default, the job file will be generated under workspace path.
            job_filename = self._get_job_filename(workspace, job.id, job_name)
            self._save_job_file(job_filename, job_content, submitter)
            job.job_file = job_filename
            job.save()
        try:
            # Generate job comment
            job_comment = JobComment(job.id)
            # Scheduler adapter only can access local file.
            # If job file exist on local path, submit from file.
            if os.path.exists(job_filename):
                job_identity = scheduler.submit_job_from_file(
                    job_filename=job_filename,
                    job_name=job_name,
                    job_comment=job_comment.get_comment())
            # If job file does not exist on local path, submit from content.
            else:
                job_identity = scheduler.submit_job(
                    job_content=job_content,
                    job_name=job_name,
                    job_comment=job_comment.get_comment())
        except SchedulerJobBaseException as e:
            job.operate_state = JobOperateState.CREATE_FAIL.value
            job.state = JobState.COMPLETED.value
            job.reason = str(e)
            job.save()
            logger.exception("Submit job failed.")
            raise SubmitJobException(job_id=job.id) from e
        # Save job identity to database
        scheduler_job = scheduler.query_job(job_identity)
        update_job_by_scheduler_job(job, scheduler_job)
        if job.operate_state == JobOperateState.CREATING.value \
                or not job.operate_state:
            job.operate_state = JobOperateState.CREATED.value
        job.save()

        EventLog.opt_create(
            request.user.username, EventLog.job, EventLog.create,
            EventLog.make_list(job.id, job_name)
        )
        # Make response
        return Response({'id': job.id})

    def _read_job_file(self, job_filename, user):
        fs_operator = get_fs_operator(user)
        job_content = fs_operator.read_content(job_filename)
        return job_content

    def _save_job_file(self, job_filename, job_content, user):
        fs_operator = get_fs_operator(user)
        with fs_operator.open_file(job_filename, 'w') as f:
            f.file_handle.write(str(job_content))
        if user.uid and user.gid:
            fs_operator.chown(job_filename, user.uid, user.gid)
            fs_operator.chmod(job_filename, stat.S_IRUSR | stat.S_IWUSR)

    def _get_job_filename(self, workspace, job_id, job_name):
        from django.utils.timezone import now
        scheduler_code = settings.LICO.SCHEDULER
        job_filename = os.path.join(
            workspace,
            '{0}_{1}_{2:%Y%m%d%H%M}.{3}'.format(
                job_name, job_id, now(), scheduler_code
            )
        )
        return job_filename
