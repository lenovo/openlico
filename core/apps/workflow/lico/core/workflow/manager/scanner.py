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
from datetime import timedelta

from ..models import Workflow, WorkflowPeriodicTask
from ..schedules import TzAwareCrontab
from ..views import Operation, _handle_workflow_operation
from .operator import cancel_workflow, scan_workflow

logger = logging.getLogger(__name__)

workflow_finished_status = (
    Workflow.CREATED,
    Workflow.FAILED,
    Workflow.CANCELLED,
    Workflow.COMPLETED
)


class WorkflowScanner(object):

    @classmethod
    def scan(cls):
        all_workflow = Workflow.objects.exclude(
            status__in=workflow_finished_status).iterator()

        for workflow in all_workflow:
            # fetch one from all_workflow
            if "starting" == workflow.status:
                workflow.status = None
                workflow.save()
                scan_workflow(workflow)

            elif "cancelling" == workflow.status:
                cancel_workflow(workflow)
                scan_workflow(workflow)

            elif workflow.status is None:
                scan_workflow(workflow)

            else:
                logger.error(
                    "Workflow status error, id: %s, error status: %s",
                    workflow.id, workflow.status)
                # workflow status error


def workflow_beat(interval):
    tasks = WorkflowPeriodicTask.objects.filter(is_enabled=True)
    now = TzAwareCrontab().now()

    last_scan_at = now - timedelta(seconds=interval)
    for task in tasks.iterator():
        # If last_run_at is None, means the task has never been triggered.
        if not task.last_run_at and task.workflow.status == Workflow.CREATED:
            operation = Operation.RUN
        else:
            operation = Operation.RERUN

        schedstate = task.schedule.is_due(last_scan_at)

        if not schedstate.is_due:
            continue  # wait for next beat

        # run or rerun the workflow
        try:
            _handle_workflow_operation(task.workflow, operation)
        except Exception:
            logger.exception(
                "Unexpected workflow {0} for the loop, the status is {1} "
                "and skip it".format(task.workflow.id, task.workflow.status)
            )
            continue
        finally:
            # disable clocked workflows once the trigger time passed
            if task.is_one_off:
                task.is_enabled = False
                task.save()

        task.last_run_at = now
        task.total_run_count += 1

        task.save()
