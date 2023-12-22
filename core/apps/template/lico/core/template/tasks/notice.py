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

from datetime import datetime

import requests
from celery.utils.log import get_task_logger
from django.conf import settings
from django.template.loader import render_to_string

from lico.auth.requests import ServiceAuth
from lico.core.base.celery import app

from ..models import JobComp

logger = get_task_logger(__name__)


@app.task(ignore_result=True)
def rest(jobcomp_id, job_info):
    jobcomp = JobComp.objects.get(id=jobcomp_id)
    if jobcomp.notice_type == JobComp.REST:
        url = jobcomp.url
        job_status = get_job_status(job_info)
        job_info.update(
            status=job_status
        )
        if url:
            res = requests.request(
                method=jobcomp.method,
                url=url,
                json=job_info,
                timeout=settings.TEMPLATE.NOTIFY_RESTAPI_TIMEOUT,
                verify=False
            )
            res.raise_for_status()


@app.task(ignore_result=True)
def lico_restapi(jobcomp_id, job_info):
    jobcomp = JobComp.objects.get(id=jobcomp_id)
    if jobcomp.notice_type == JobComp.LICO_REST:
        url = jobcomp.url
        job_status = get_job_status(job_info)
        job_info.update(
            status=job_status
        )
        if url:
            auth = ServiceAuth(
                secret=settings.WEB_SECRET_KEY,
                username=job_info.get('submitter')
            )
            res = requests.request(
                method=jobcomp.method,
                url=url,
                json=job_info,
                timeout=settings.TEMPLATE.NOTIFY_RESTAPI_TIMEOUT,
                auth=auth,
                verify=False
            )
            res.raise_for_status()


@app.task(ignore_result=True)
def email(jobcomp_id, job_info):
    jobcomp = JobComp.objects.get(id=jobcomp_id)
    if jobcomp.notice_type == JobComp.EMAIL:
        from lico.core.contrib.client import Client
        user = Client().auth_client().get_user_info(
            username=job_info['submitter']
        )
        target = user.email
        if target:
            start_time = datetime.utcfromtimestamp(
                int(job_info['start_time'])
            )
            end_time = datetime.utcfromtimestamp(
                int(job_info['end_time'])
            )
            submit_time = datetime.utcfromtimestamp(
                int(job_info['submit_time'])
            )
            job_status = get_job_status(job_info)
            job_info.update(
                start_time=start_time,
                end_time=end_time,
                submit_time=submit_time,
                status=job_status
            )
            Client().mail_client().send_message(
                target=[target],
                title=render_to_string(
                    'notice/email_title.html',
                    context=job_info
                ),
                msg=render_to_string(
                    'notice/email.html',
                    context=job_info
                )
            )
        else:
            logger.warning('Email address does not exist')


def get_job_status(job):
    job_state = job['state']
    op_state = job['operate_state']
    if op_state == '':
        op_state = "creating"

    job_state_mapping = {
        "c": "completed",
        "r": "running",
        "q": "queueing",
        "s": "suspending",
        "w": "waiting",
        "h": "holding"
    }

    op_state_mapping = {
        "cancelling": "cancelling",
        "creating": "creating",
        "cancelled": "cancelled",
        "create_fail": "createfailed"
    }

    if job_state.lower() in job_state_mapping:
        status = job_state_mapping[job_state.lower()]
    if op_state.lower() in op_state_mapping:
        status = op_state_mapping[op_state.lower()]
    return status
