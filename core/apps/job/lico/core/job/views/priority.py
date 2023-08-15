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
from rest_framework.response import Response

from lico.core.contrib.eventlog import EventLog
from lico.core.contrib.permissions import AsOperatorRole
from lico.core.contrib.schema import json_schema_validate
from lico.scheduler.base.exception.job_exception import (
    InvalidPriorityException,
)

from ..exceptions import (
    AdjustJobPriorityException, InvalidJobPriorityException,
    QueryJobPriorityException,
)
from ..helpers.scheduler_helper import get_admin_scheduler
from .job_view import JobBaseActionView

logger = logging.getLogger(__name__)


class PriorityView(JobBaseActionView):
    permission_classes = (AsOperatorRole,)

    def get(self, request):
        scheduler = get_admin_scheduler()
        try:
            priority_dict = scheduler.get_priority_value()
        except Exception:
            raise QueryJobPriorityException
        return Response(priority_dict)

    @json_schema_validate({
        "type": "object",
        "properties": {
            "job_ids": {
                "type": "array",
                "items": {"type": ["integer"]}
            },
            "priority_value": {
                "type": "string",
                'pattern': r'^-?\d+$'
            }
        },
        "required": ["job_ids", "priority_value"]
    })
    @atomic
    def post(self, request, *args, **kwargs):
        priority_value = request.data["priority_value"]
        job_query, scheduler = self.get_jobs_and_scheduler(
            request.data['job_ids'], request.user)
        exec_jobs_dict = self.get_exec_jobs_dict(job_query)
        try:
            status = scheduler.update_job_priority(
                exec_jobs_dict.keys(), priority_value
            )
        except InvalidPriorityException:
            raise InvalidJobPriorityException
        except Exception as e:
            logger.exception('Failed to set the job priority, reason: %s' % e)
            raise AdjustJobPriorityException
        job_query.update(priority=priority_value)
        EventLog.opt_create(
            request.user.username, EventLog.job, EventLog.priority,
            exec_jobs_dict.values()
        )
        return Response({"action_status": status})
