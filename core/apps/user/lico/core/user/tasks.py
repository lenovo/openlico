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

from celery.utils.log import get_task_logger

from lico.core.base.celery import app

logger = get_task_logger(__name__)


@app.task(ignore_result=True, time_limit=3600)
def import_record_task(task_id, operator_username):  # pragma: no cover
    from .models import ImportRecordTask
    from .utils import import_record
    task = ImportRecordTask.objects.get(id=task_id)
    import_record(task, operator_username)
