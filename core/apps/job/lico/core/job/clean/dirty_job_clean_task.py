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

from django.db.models import Q

from ..base.job_operate_state import JobOperateState
from ..base.job_state import JobState
from ..models import Job

logger = logging.getLogger(__name__)


class CleanDirtyJobTask:

    def _clean_cancelling_job(self):
        try:
            Job.objects.filter(
                Q(state__in=JobState.get_final_state_values())
                & Q(operate_state=JobOperateState.CANCELLING.value)
            ).update(operate_state=JobOperateState.CANCELLED.value)
        except Exception:
            logger.exception("Clean cancelling job failed.")

    def clean_dirty_job(self):
        self._clean_cancelling_job()
