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

# from lico.core.contrib.eventlog import EventLog
from lico.core.contrib.permissions import AsOperatorRole
from lico.core.contrib.schema import json_schema_validate
from lico.core.contrib.views import APIView
from lico.scheduler.base.exception.job_exception import (
    InvalidPriorityException,
)

from ..exceptions import (
    AdjustJobPriorityException, InvalidJobPriorityException,
    QueryJobPriorityException,
)
from ..helpers.scheduler_helper import get_admin_scheduler
from ..models import Job

logger = logging.getLogger(__name__)


class PriorityView(APIView):
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
            "scheduler_ids": {
                "type": "array",
                "items": {"type": ["string"]}
            },
            "priority_value": {
                "type": "string",
                'pattern': r'^-?\d+$'
            }
        },
        "required": ["scheduler_ids", "priority_value"]
    })
    @atomic
    def post(self, request, *args, **kwargs):
        data = request.data
        scheduler_ids = data["scheduler_ids"]
        priority_value = data["priority_value"]
        scheduler = get_admin_scheduler()
        try:
            query = Job.objects.filter(
                delete_flag=False, scheduler_id__in=scheduler_ids
            )
            scheduler.update_job_priority(scheduler_ids, priority_value)
        except InvalidPriorityException:
            raise InvalidJobPriorityException
        except Exception as e:
            logger.exception('Failed to set the job priority, reason: %s' % e)
            raise AdjustJobPriorityException
        else:
            query.update(priority=priority_value)
        # for job in query:
        #     EventLog.opt_create(
        #         request.user.username, EventLog.job, EventLog.priority,
        #         EventLog.make_list(job.id, job.job_name)
        #     )
        return Response()
