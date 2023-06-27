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

from django.db import transaction
from rest_framework.response import Response

from lico.core.contrib.schema import json_schema_validate
from lico.core.contrib.views import InternalAPIView

from ..base.job_state import JobState
from ..exceptions import SyncHistoryJobException
from ..helpers.job_helper import (
    update_history_job_by_scheduler_job, update_job_by_scheduler_job,
)
from ..helpers.scheduler_helper import get_admin_scheduler
from ..models import Job

logger = logging.getLogger(__name__)


class SyncHistoryJobView(InternalAPIView):
    @json_schema_validate({
        "type": "object",
        "properties": {
            "start_time": {"type": "integer"},
            "end_time": {"type": "integer"},
            "exclude_ids": {
                "type": "array",
                "items": {"type": ["string", "null"]}
            }
        },
        "required": ["start_time", "end_time", "exclude_ids"]
    })
    def post(self, request):
        try:
            scheduler_job_list = get_admin_scheduler().get_history_job(
                request.data['start_time'], request.data['end_time']
            )
        except Exception as e:
            logger.exception('Get history job failed.')
            raise SyncHistoryJobException from e
        exclude_ids = [int(ex_id) for ex_id in request.data['exclude_ids']]
        jobs_id = []
        for scheduler_job in scheduler_job_list:
            job_identity_str = scheduler_job.identity.to_string()
            job_state = JobState.from_scheduler_job_state(scheduler_job.state)
            if job_state.value not in JobState.get_final_state_values():
                continue
            with transaction.atomic():
                query_jobs = Job.objects.filter(identity_str=job_identity_str)
                for query_job in query_jobs:
                    if query_job.id in exclude_ids:
                        jobs_id.append(query_job.id)
                        break
                    # update some field for job
                    update_history_job_by_scheduler_job(
                        query_job, scheduler_job
                    )
                    jobs_id.append(query_job.id)
                    break
                else:
                    job = Job.objects.create(job_name=scheduler_job.name[:128])
                    update_job_by_scheduler_job(job, scheduler_job)
                    job.save()
                    jobs_id.append(job.id)
                    logger.info(
                        "Sync history job finished. Job id: %d, "
                        "Scheduler id: %s", job.id,
                        scheduler_job.identity.get_display()
                    )
        return Response(jobs_id)
