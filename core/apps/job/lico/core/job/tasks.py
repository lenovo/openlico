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

from django.conf import settings

from .clean.dirty_job_clean_task import CleanDirtyJobTask
from .sync.full_job_sync_task import FullJobSyncTask
from .sync.owns_job_sync_task import OwnsJobSyncTask

logger = logging.getLogger(__name__)


def job_sync_task():  # pragma: no cover
    logger.info("Trigger Job Sync Task")
    start = time.time()
    if settings.JOB.JOB_SYNC_MODE == "full":
        task = FullJobSyncTask()
    if settings.JOB.JOB_SYNC_MODE == "owns":
        task = OwnsJobSyncTask()
    task.sync_job()
    CleanDirtyJobTask().clean_dirty_job()
    end = time.time()
    logger.info(f"Job Sync Task End, Duration: {end - start}s")
