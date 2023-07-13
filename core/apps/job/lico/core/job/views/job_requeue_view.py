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

from django.db.transaction import atomic
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

# from lico.core.contrib.eventlog import EventLog
from lico.core.contrib.permissions import AsOperatorRole
from lico.core.contrib.schema import json_schema_validate
from lico.core.user.models import User

from ..exceptions import InvalidUserRoleException, RequeueJobException
from ..models import Job
from .job_view import JobBaseActionView

logger = logging.getLogger(__name__)


class JobRequeueView(JobBaseActionView):

    @json_schema_validate({
        "type": "object",
        "properties": {
            "role": {
                "type": "string",
                "enum": ["admin", "operator", "user"],
                "default": "user"
            },
            "job_ids": {
                "type": "array",
                "items": {"type": ["integer"]}
            }
        },
        "required": ["role", "job_ids"]
    })
    @atomic
    def post(self, request):
        user = request.user
        data = request.data
        current_role = data.get("role")
        if (not current_role) or \
                (User.ROLE_NAMES.get(current_role) > user.role):
            raise InvalidUserRoleException

        job_ids = data.get("job_ids")
        scheduler = self.get_job_scheduler(user, current_role)

        try:
            query = Job.objects.filter(
                delete_flag=False,
                id__in=job_ids,
            )
            if User.ROLE_NAMES.get(current_role) < AsOperatorRole.floor:
                if query.count() != \
                        query.filter(submitter=user.username).count():
                    raise PermissionDenied

            scheduler_ids = query.values_list('scheduler_id', flat=True)
            scheduler.requeue_job(scheduler_ids)

        except Exception as e:
            logger.exception('Failed to requeue the job, reason: %s' % e)
            raise RequeueJobException

        # for job in query:
        #     EventLog.opt_create(
        #         request.user.username,
        #         EventLog.job,
        #         EventLog.requeue,
        #         EventLog.make_list(job.id, job.job_name)
        #     )
        return Response()
