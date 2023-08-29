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

from lico.core.contrib.client import Client

from ..models import Workflow
from .state import JobOperateState, JobState

logger = logging.getLogger(__name__)

job_running_state = JobState.get_waiting_state_values()
job_finished_state = JobState.get_final_state_values()
job_operate_state = {
    "CG": JobOperateState.CREATING.value,
    "CF": JobOperateState.CREATE_FAIL.value,
    "CD": JobOperateState.CREATED.value,
    "CAG": JobOperateState.CANCELLING.value,
    "CAD": JobOperateState.CANCELLED.value
}


def cancel_workflow(workflow):
    job_client = Client().job_client(username=workflow.owner)
    steps = workflow.workflow_steps.iterator()
    for step in steps:
        step_jobs_query = step.step_job
        if step_jobs_query.count() > 0:
            jobs_id = step_jobs_query.values_list(
                "job_id", flat=True
            )
            for job_id in jobs_id:
                if job_id in [None, -1]:
                    continue
                try:
                    job_dict = job_client.query_job(job_id)
                except Exception:
                    logger.exception('query job error, id:%s', job_id)
                else:
                    if job_dict['state'] in job_running_state:
                        try:
                            job_client.cancel_job(job_id)
                            logger.info('cancelled a job, id: %s', job_id)
                        except Exception:
                            logger.exception('cancel job error, id:%s', job_id)


def scan_workflow(workflow):
    steps = workflow.workflow_steps.order_by('order').iterator()
    step_dict = {
        "running_job_list": [],
        "to_be_failed": False,
        "to_be_cancelled": True if workflow.status == Workflow.CANCELLING
        else False
    }
    for step in steps:
        step_jobs_query = step.step_job.order_by("id")
        if step_jobs_query.count() <= 0:
            continue

        for step_job in step_jobs_query.iterator():
            if step_job.job_id is None:
                # step_job.job_id is None, submit job
                _submit_job(
                    workflow.owner, step_job, step_dict, workflow.run_policy)
            else:
                # step_job.job_id is integer, step_job has been created
                _query_job(
                    workflow.owner, step_job, step_dict, workflow.run_policy)

            if len(step_dict['running_job_list']) >= workflow.max_submit_jobs:
                # step has enough running step_job
                return
        if len(step_dict['running_job_list']):
            # step has running step_job
            return

    if step_dict["to_be_cancelled"]:
        workflow.status = Workflow.CANCELLED
        workflow.save()
        return
    if step_dict["to_be_failed"]:
        workflow.status = Workflow.FAILED
        workflow.save()
        return
    workflow.status = Workflow.COMPLETED
    workflow.save()


def _query_job(owner, step_job, step_dict, run_policy):
    if step_job.job_id == -1:
        if Workflow.ALL_COMPLETED == run_policy:
            step_dict['to_be_failed'] = True
        return

    job_client = Client().job_client(username=owner)
    try:
        query_result = job_client.query_job(step_job.job_id)
    except Exception as e:
        logger.exception('query job error, id: %s', step_job.job_id)
        logger.exception(e)
    else:
        if query_result['state'] in job_running_state:
            step_dict["running_job_list"].append(step_job.job_id)
        elif query_result['state'] in job_finished_state:
            if query_result['operate_state'] == job_operate_state['CF']:
                if Workflow.ALL_COMPLETED == run_policy:
                    step_dict['to_be_failed'] = True
            elif query_result['operate_state'] in [
                job_operate_state['CAD'], job_operate_state['CAG']
            ]:
                step_dict['to_be_cancelled'] = True
            # then completed


def _submit_job(owner, step_job, step_dict, run_policy):
    if step_dict["to_be_failed"] or step_dict['to_be_cancelled']:
        # has failed or cancelled job, quit
        return
    template_client = Client().template_client(username=owner)
    try:
        submit_result = template_client.submit_template_job(
            step_job.template_id, step_job.json_body)
        logger.info(
            'submit step_job completed, job_id: %s',
            submit_result['id'])
        step_job.job_id = submit_result['id']
        step_job.save()
        step_dict["running_job_list"].append(submit_result['id'])

    except Exception:
        # create job failed, save a especial job_id
        step_job.job_id = -1
        step_job.save()
        if Workflow.ALL_COMPLETED == run_policy:
            step_dict["to_be_failed"] = True
        logger.exception(
            'submit step_job error, id: %s, name: %s',
            step_job.id, step_job.job_name)
