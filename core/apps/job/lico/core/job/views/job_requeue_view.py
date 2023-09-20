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

import logging

from django.db.transaction import atomic
from rest_framework.response import Response

from lico.core.contrib.eventlog import EventLog
from lico.core.contrib.schema import json_schema_validate
from lico.scheduler.base.exception.job_exception import (
    OperationNotSupportException,
)

from ..exceptions import JobOperationNotSupportException, RequeueJobException
from .job_view import JobBaseActionView

logger = logging.getLogger(__name__)


class JobRequeueView(JobBaseActionView):

    @json_schema_validate({
        "type": "object",
        "properties": {
            "job_ids": {
                "type": "array",
                "items": {"type": ["integer"]}
            }
        },
        "required": ["job_ids"]
    })
    @atomic
    def post(self, request):
        job_query, scheduler = self.get_jobs_and_scheduler(
            request.data['job_ids'], request.user)
        exec_jobs_dict = self.get_exec_jobs_dict(job_query)
        try:
            status = scheduler.requeue_job(exec_jobs_dict.keys())
        except OperationNotSupportException:
            raise JobOperationNotSupportException
        except Exception as e:
            logger.exception('Failed to requeue the job, reason: %s' % e)
            raise RequeueJobException

        EventLog.opt_create(
            request.user.username,
            EventLog.job,
            EventLog.requeue,
            exec_jobs_dict.values()
        )
        return Response({"action_status": status})
