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

import pytz
from dateutil import parser
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.response import Response

from lico.core.contrib.schema import json_schema_validate
from lico.core.contrib.views import APIView, DataTableView

from . import schedules
from .exceptions import (
    CreateWorkflowException, CreateWorkflowStepException,
    CreateWorkflowStepJobException, WorkflowOperationException,
    WorkflowStepAlreadyExist, WorkflowSummaryInfoMissingException,
)
from .models import (
    ClockedSchedule, CrontabSchedule, Workflow, WorkflowPeriodicTask,
    WorkflowStep, WorkflowStepJob,
)

logger = logging.getLogger(__name__)


class WorkflowPeriodicTaskMixin(object):
    def get_or_create_schedule(self):
        """ Returns a dict with either crontab or clocked schedule according to
        request body data.
        """
        kws = {}
        try:
            if 'crontab' in self.request.data:
                m, h, dom, mon, dow = self.request.data['crontab'].split()
                if settings.USE_TZ:
                    sched = schedules.TzAwareCrontab
                else:
                    sched = schedules.crontab

                crontab = CrontabSchedule.from_schedule(sched(
                    minute=m,
                    hour=h,
                    day_of_week=dow,
                    day_of_month=dom,
                    month_of_year=mon,
                    tz=pytz.timezone(self.request.data['tz']),
                ))
                if crontab.id is None:
                    crontab.save()

                kws["crontab"] = crontab
            elif 'clocked' in self.request.data:
                ts = parser.parse(self.request.data['clocked'])
                clocked = ClockedSchedule.from_schedule(schedules.clocked(ts))
                if clocked.id is None:
                    clocked.save()

                kws["clocked"] = clocked
        except Exception as e:
            raise IntegrityError from e

        return kws

    def create_workflowperiodictask(self, workflow):
        """
        Returns the WorkflowPeriodicTask instance if we have
        a schedule to create according to request body data.
        """
        kws = {
            "workflow": workflow,
        }
        schedule_kws = self.get_or_create_schedule()
        if not schedule_kws:
            return

        kws.update(**schedule_kws)

        return WorkflowPeriodicTask.objects.create(**kws)

    def edit_workflowperiodictask(self, task):
        """ Edits the schedule on given task according to request body data.
        """
        schedule_kws = self.get_or_create_schedule()
        if not schedule_kws:
            return

        # Clear the old schedule before setting the new schedule
        task.crontab = task.clocked = None
        # we might have a crontab OR a clocked schedule
        for k, v in schedule_kws.items():
            setattr(task, k, v)

        # Always enable the existed policy
        task.is_enabled = True

        task.save()

        return task


class WorkflowView(WorkflowPeriodicTaskMixin, DataTableView):
    columns_mapping = {  # <display field name>: <DB field name>
        "id": "id",
        "name": "name",
        "status": "status",
        "create_time": "create_time",
        "description": "description",
    }

    def trans_result(self, result):
        workflow_dict = result.as_dict(
            inspect_related=False
        )
        workflow_dict['step_number'] = result.workflow_steps.count()
        if workflow_dict['status'] is None:
            workflow_dict['status'] = "running"

        workflow_dict['periodic_task'] = result.get_periodic_task()

        return workflow_dict

    def get_query(self, request, *args, **kwargs):
        return Workflow.objects.filter(owner=request.user.username)

    @json_schema_validate({
        'type': 'object',
        'properties': {
            'name': {
                'type': 'string',
                'minLength': 1
            },
            'max_submit_jobs': {
                'type': 'number',
                'minimum': 0
            },
            'description': {
                'type': 'string'
            },
            # format 'm h  dom mon dow'
            'crontab': {
                'type': 'string',
            },
            'clocked': {
                'type': 'string',
            },
            'tz': {
                'type': 'string',
            },
        },
        'required': ['name', 'max_submit_jobs', 'description']
    })
    def post(self, request):
        with transaction.atomic():
            try:
                workflow = Workflow.objects.create(
                    name=request.data['name'],
                    owner=request.user.username,
                    run_policy=Workflow.ALL_COMPLETED,
                    max_submit_jobs=request.data['max_submit_jobs'],
                    status=Workflow.CREATED,
                    description=request.data['description']
                )

                if request.data.get('crontab') and request.data.get('clocked'):
                    logger.exception('Provide just one schedule, not both.')
                    raise CreateWorkflowException

                self.create_workflowperiodictask(workflow)

            except IntegrityError as e:
                logger.exception('Create workflow failed')
                raise CreateWorkflowException from e

        return Response(self.trans_result(workflow))


class Operation:
    RUN = "run"
    RERUN = "rerun"
    CANCEL = "cancel"
    COPY = "copy"


@transaction.atomic  # noqa: C901
def _handle_workflow_operation(workflow, operation):
    if operation not in (
        Operation.RUN,
        Operation.RERUN,
        Operation.CANCEL,
    ):
        raise WorkflowOperationException(
            f"does not support specified operation {operation}"
        )

    before_status = workflow.status
    workflow_steps = workflow.workflow_steps
    step_number = workflow_steps.count()

    def _update_last_run_at(trigger_time):
        if workflow.get_periodic_task():
            workflow.workflowperiodictask.last_run_at = trigger_time
            workflow.workflowperiodictask.save()

    if operation == Operation.RUN:
        if before_status != Workflow.CREATED:
            raise WorkflowOperationException(
                f"Workflow's current status {before_status} "
                f"does not support specified operation {operation}"
            )

        workflow.status = Workflow.STARTING
        workflow.start_time = timezone.now()
        _update_last_run_at(workflow.start_time)
    elif operation == Operation.RERUN:
        if before_status not in [Workflow.CANCELLED,
                                 Workflow.COMPLETED, Workflow.FAILED]:
            raise WorkflowOperationException(
                f"Workflow's current status {before_status} "
                f"does not support specified operation {operation}"
            )

        for step in workflow_steps.iterator():
            for step_job in step.step_job.iterator():
                step_job.job_id = None
                step_job.save()

        workflow.status = Workflow.STARTING
        workflow.start_time = timezone.now()
        _update_last_run_at(workflow.start_time)
    elif operation == Operation.CANCEL:
        if before_status not in [Workflow.STARTING, None]:
            raise WorkflowOperationException(
                f"Workflow's current status {before_status} "
                f"does not support specified operation {operation}"
            )
        workflow.status = Workflow.CANCELLING

    workflow.save()
    ret_dict = workflow.as_dict(inspect_related=False)
    ret_dict['step_number'] = step_number
    return ret_dict


class WorkflowDetailView(WorkflowPeriodicTaskMixin, APIView):
    def get(self, request, workflow_id):
        workflow = Workflow.objects.get(id=workflow_id)
        ret_dict = workflow.as_dict(inspect_related=False)
        if ret_dict['status'] is None:
            ret_dict['status'] = 'running'
        ret_dict['step'] = workflow.workflow_steps.as_dict(
            exclude=['workflow'])

        ret_dict['periodic_task'] = workflow.get_periodic_task()

        return Response(ret_dict)

    @json_schema_validate({
        'type': 'object',
        'properties': {
            'operation': {
                'type': 'string',
                "enum": [
                    Operation.RUN,
                    Operation.RERUN,
                    Operation.CANCEL,
                    Operation.COPY,
                ]
            },
            'name': {
                'type': 'string',
                'minLength': 1
            },
            'description': {
                'type': 'string',
            }
        },
        'required': ['operation']
    })
    def post(self, request, workflow_id):
        workflow = Workflow.objects.get(id=workflow_id)
        operation = request.data['operation']

        if operation == Operation.COPY:
            ret_dict = self._copy_workflow(request, workflow)
            return Response(ret_dict)

        data = _handle_workflow_operation(workflow, operation)
        return Response(data)

    @json_schema_validate({
        'type': 'object',
        'properties': {
            'name': {
                'type': 'string',
                'minLength': 1
            },
            'max_submit_jobs': {
                'type': 'number',
                'minimum': 1
            },
            'description': {
                'type': 'string'
            },
        },
        'required': ['name', 'max_submit_jobs', 'description']
    })
    def put(self, request, workflow_id):
        with transaction.atomic():
            workflow = Workflow.objects.get(id=workflow_id)
            workflow.name = request.data['name']
            workflow.max_submit_jobs = request.data['max_submit_jobs']
            workflow.description = request.data['description']
            workflow.save()

            # Change the workflow to manual mode while request without periodic
            if 'crontab' not in request.data and 'clocked' not in request.data:
                if hasattr(workflow, 'workflowperiodictask'):
                    workflow.workflowperiodictask.delete()

            try:
                self.edit_workflowperiodictask(workflow.workflowperiodictask)
            except WorkflowPeriodicTask.DoesNotExist:
                # Refer to request, try to bind new periodic task
                self.create_workflowperiodictask(workflow)

        ret_dict = workflow.as_dict(inspect_related=False)
        return Response(ret_dict)

    def delete(self, request, workflow_id):
        with transaction.atomic():
            Workflow.objects.get(id=workflow_id).delete()
        return Response()

    def _copy_workflow(self, request, old_workflow):
        try:
            name = request.data['name']
            max_submit_jobs = request.data['max_submit_jobs']
            description = request.data['description']
        except Exception as e:
            logger.error("The Workflow is missing summary information")
            raise WorkflowSummaryInfoMissingException from e
        with transaction.atomic():
            new_workflow = Workflow.objects.create(
                name=name,
                owner=request.user.username,
                run_policy=old_workflow.run_policy,
                max_submit_jobs=max_submit_jobs,
                status=Workflow.CREATED,
                description=description
            )
            self.create_workflowperiodictask(new_workflow)

            self._create_step_and_stepjob(old_workflow, new_workflow)
            return new_workflow.as_dict(inspect_related=False)

    def _create_step_and_stepjob(self, old_workflow, new_workflow):
        for old_step in old_workflow.workflow_steps.iterator():
            new_step = WorkflowStep.objects.create(
                name=old_step.name,
                order=old_step.order,
                workflow=new_workflow,
                description=old_step.description
            )
            new_job_list = []
            for old_job in old_step.step_job.iterator():
                new_job_list.append(
                    WorkflowStepJob(
                        workflow_step=new_step,
                        job_name=old_job.job_name,
                        template_id=old_job.template_id,
                        json_body=old_job.json_body
                    )
                )
            WorkflowStepJob.objects.bulk_create(new_job_list)


class WorkflowStepView(APIView):
    @json_schema_validate({
        'type': 'object',
        'properties': {
            'name': {
                'type': 'string',
                'minLength': 1
            },
            'order': {
                'type': 'number',
                'minimum': 1
            },
            'description': {
                'type': 'string'
            },
        },
        'required': ['name', 'order', 'description']
    })
    def post(self, request, workflow_id):
        order = request.data['order']
        workflow = Workflow.objects.get(id=workflow_id)
        if workflow.workflow_steps.filter(order=order):
            logger.exception('This Workflow Step %s is already exist', order)
            raise WorkflowStepAlreadyExist
        with transaction.atomic():
            try:
                step = WorkflowStep.objects.create(
                    name=request.data['name'],
                    order=order,
                    workflow=workflow,
                    description=request.data['description']
                )
            except IntegrityError as e:
                logger.exception('Create workflow step failed')
                raise CreateWorkflowStepException from e
        ret_dict = step.as_dict(inspect_related=False)
        return Response(ret_dict)

    @json_schema_validate({
        'type': 'object',
        'properties': {
            'id': {
                'type': 'number',
                'minimum': 1
            },
            'name': {
                'type': 'string',
                'minLength': 1
            },
            'order': {
                'type': 'number',
                'minimum': 1
            },
            'description': {
                'type': 'string'
            },
        },
        'required': ['id', 'name', 'order', 'description']
    })
    def put(self, request, workflow_id):
        step_id = request.data['id']
        order = request.data['order']
        if WorkflowStep.objects.filter(
                workflow_id=workflow_id, order=order).exclude(id=step_id):
            logger.exception('This Workflow Step %s is already exist',
                             order)
            raise WorkflowStepAlreadyExist
        with transaction.atomic():
            step = WorkflowStep.objects.filter(workflow_id=workflow_id).get(
                id=step_id)
            step.name = request.data['name']
            step.order = order
            step.description = request.data['description']
            step.save()

        ret_dict = step.as_dict(inspect_related=False)
        return Response(ret_dict)

    @json_schema_validate({
        'type': 'object',
        'properties': {
            'id': {
                'type': 'number',
                'minimum': 1
            },
        },
        'required': ['id']
    })
    def delete(self, request, workflow_id):
        step_id = request.data['id']
        with transaction.atomic():
            WorkflowStep.objects.filter(
                workflow_id=workflow_id).get(id=step_id).delete()
        return Response()


class WorkflowStepJobView(APIView):
    @json_schema_validate({
        'type': 'object',
        'properties': {
            'template_id': {
                'type': 'string',
                'minLength': 1
            },
            'json_body': {
                "type": "object",
                "properties": {
                    'job_name': {
                        'type': 'string',
                    }
                },
                'required': ['job_name']
            },
        },
        'required': ['template_id', 'json_body']
    })
    def post(self, request, step_id):
        json_body = request.data['json_body']
        with transaction.atomic():
            step = WorkflowStep.objects.get(id=step_id)
            try:
                job = WorkflowStepJob.objects.create(
                    workflow_step=step,
                    job_name=json_body['job_name'],
                    template_id=request.data['template_id'],
                    json_body=json_body,
                )
            except IntegrityError as e:
                logger.exception('Create workflow step job failed')
                raise CreateWorkflowStepJobException from e
        ret_dict = job.as_dict(inspect_related=False)

        return Response(ret_dict)

    @json_schema_validate({
        'type': 'object',
        'properties': {
            'id': {
                'type': 'number',
                'minimum': 1
            },
            'json_body': {
                "type": "object",
                "properties": {
                    'job_name': {
                        'type': 'string',
                    }
                },
                'required': ['job_name']
            },
        },
        'required': ['id', 'json_body']
    })
    def put(self, request, step_id):
        step_job_id = request.data['id']
        json_body = request.data['json_body']
        with transaction.atomic():
            job = WorkflowStepJob.objects.filter(
                workflow_step_id=step_id).get(id=step_job_id)
            job.job_name = json_body['job_name']
            job.json_body = json_body

            job.save()

        ret_dict = job.as_dict(inspect_related=False)
        return Response(ret_dict)

    @json_schema_validate({
        'type': 'object',
        'properties': {
            'id': {
                'type': 'number',
                'minimum': 1
            },
        },
        'required': ['id']
    })
    def delete(self, request, step_id):
        step_job_id = request.data['id']
        with transaction.atomic():
            WorkflowStepJob.objects.filter(
                workflow_step_id=step_id).get(id=step_job_id).delete()
        return Response()


class WorkflowStepJobMoveView(APIView):
    @json_schema_validate({
        'type': 'object',
        'properties': {
            'job_id': {
                'type': 'integer',
                'minimum': 1
            },
            'new_step_id': {
                'type': 'integer',
                'minimum': 1
            },
        },
        'required': ['job_id', 'new_step_id']
    })
    def put(self, request, step_id):
        step_job_id = request.data['job_id']
        new_step_id = request.data['new_step_id']
        with transaction.atomic():
            job = WorkflowStepJob.objects.filter(
                workflow_step_id=step_id).get(id=step_job_id)
            job.workflow_step_id = new_step_id
            job.save()

        ret_dict = job.as_dict(inspect_related=False)
        return Response(ret_dict)

