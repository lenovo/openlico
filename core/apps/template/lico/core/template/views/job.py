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

import json
import logging
import os

from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from lico.core.contrib.authentication import (
    RemoteApiKeyAuthentication, RemoteJWTInternalAuthentication,
    RemoteJWTWebAuthentication,
)
from lico.core.contrib.client import Client
from lico.core.contrib.schema import json_schema_validate
from lico.core.contrib.views import APIView, InternalAPIView

from ..exceptions import (
    JobFileNotExist, SubmitJobException, TemplateException, TemplateNotExist,
)
from ..helpers.fs_operator_helper import get_fs_operator
from ..models import JobComp, Template, TemplateJob, UserTemplate
from ..tasks import notice
from ..utils.common import convert_myfolder
from ..utils.notice_utils import JSON_SCHEMA_HOOKS, save_notice_job
from ..utils.template_utils import template_render

logger = logging.getLogger(__name__)


class JobViewMixin(object):
    def _preprocess_path(self, user, params, param_vals):
        fopr = get_fs_operator(user)
        ids = [
            param['id'] for param in params
            if param['dataType'] in ['folder', 'file', 'image']
        ]

        def func(item):
            key, value = item
            return key, convert_myfolder(fopr, user, value) \
                if key in ids else value

        return dict(map(func, param_vals.items()))


class SubmitJobView(JobViewMixin, APIView):
    authentication_classes = (
        RemoteJWTWebAuthentication,
        RemoteJWTInternalAuthentication,
        RemoteApiKeyAuthentication
    )

    @json_schema_validate({
        "type": "object",
        "properties": {
            "parameters": {
                "type": "object",
                "properties": {
                    "job_name": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 64
                    }
                },
                "required": ["job_name"]
            },
            "template_id": {
                "type": "string"
            },
            "hooks": JSON_SCHEMA_HOOKS
        },
        "required": [
            "parameters", "template_id"
        ]
    })
    def post(self, request):
        user = request.user
        hooks = request.data.get('hooks', [])
        # Query template
        template_id = request.data['template_id']
        if template_id.isdigit():
            template = UserTemplate.objects.filter(
                Q(username=request.user.username) | Q(type='public')
            ).get(id=int(template_id))
            params = json.loads(template.parameters_json)
        else:
            try:
                template = Template.objects.filter(enable=True).get(
                    code=template_id
                )
                params = json.loads(template.params) \
                    if template.params is not None else []
            except Template.DoesNotExist as e:
                raise TemplateNotExist from e
        # Process parameters
        raw_param_vals = request.data["parameters"]
        if template_id in ["ai_tensorflow", "ai_tensorflow2", "ai_mxnet",
                           "ai_chainer", "ai_paddlepaddle"] \
                and raw_param_vals.get("distributed") is False:
            raw_param_vals["nodes"] = 1
        param_vals = self._preprocess_path(user, params, raw_param_vals)

        if template_id == 'linpack_hpl':
            param_vals['wdir'] = os.path.dirname(param_vals['benchmark_file'])

        # Render job content
        if template_id != 'general':
            template_content = template.template_file
            # Render job file content
            job_content = template_render(
                user, template_content, param_vals)

        # Submit job
        with transaction.atomic():
            job_client = Client().job_client(username=user.username)
            if template_id == 'general':
                ret = job_client.submit_job_file(
                    job_name=param_vals['job_name'],
                    job_file=param_vals["job_file"]
                )
            else:
                ret = job_client.submit_job(
                    job_name=param_vals['job_name'],
                    workspace=param_vals['job_workspace'],
                    job_content=job_content
                )
            job_id = ret["id"]
            # Save template job
            template_obj = TemplateJob.objects.create(
                job_id=job_id,
                template_code=template_id,
                username=request.user.username,
                json_body=json.dumps(
                    dict(
                        parameters=raw_param_vals,
                        template_id=template_id,
                        hooks=hooks
                    )
                )
            )
            # Set notify
            save_notice_job(hooks, job_id)
            # Get return job
            job = job_client.query_job(job_id)
        return Response({
            'id': job_id,
            'job_file': job['job_file'],
            'template_job_id': template_obj.id
        })


class PreviewJobView(JobViewMixin, APIView):
    authentication_classes = (
        RemoteJWTWebAuthentication,
        RemoteJWTInternalAuthentication,
        RemoteApiKeyAuthentication
    )

    @json_schema_validate({
        "type": "object",
        "properties": {
            "parameters": {
                "type": "object",
                "properties": {
                    "job_name": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 64
                    }
                },
                "required": ["job_name"]
            },
            "template_id": {
                "type": "string"
            },
        },
        "required": [
            "parameters", "template_id"
        ]
    })
    def post(self, request):
        user = request.user
        # Query template
        template_id = request.data['template_id']
        if template_id.isdigit():
            template = UserTemplate.objects.filter(
                Q(username=request.user.username) | Q(type='public')
            ).get(id=int(template_id))
            params = json.loads(template.parameters_json)
        else:
            try:
                template = Template.objects.filter(enable=True).get(
                    code=template_id
                )
                params = json.loads(template.params) \
                    if template.params is not None else []
            except Template.DoesNotExist as e:
                raise TemplateNotExist from e
        # Process parameters
        raw_param_vals = request.data["parameters"]
        param_vals = self._preprocess_path(user, params, raw_param_vals)

        if template_id == 'linpack_hpl':
            param_vals['wdir'] = os.path.dirname(param_vals['benchmark_file'])

        # Render job content
        if template_id != 'general':
            template_content = template.template_file
            # Render job file content
            job_content = template_render(
                user, template_content, param_vals)
        else:
            with open(param_vals["job_file"], "r") as f:
                job_content = f.read()

        return Response(job_content)


class RerunJobView(APIView):
    def post(self, request, jobid):
        submitter = request.user
        # Query template job
        try:
            template_job = TemplateJob.objects.get(
                job_id=jobid
            )
            if template_job.username != submitter.username:
                raise PermissionDenied(
                    "No access of template job: " + str(jobid)
                )
        except TemplateJob.DoesNotExist:
            template_job = None
        # Rerun job
        job_client = Client().job_client(username=submitter.username)
        ret = job_client.rerun_job(
            jobid
        )
        if 'errid' in ret:
            err_mapping = {
                '2001': JobFileNotExist,
                '7004': SubmitJobException
            }
            raise err_mapping.get(ret['errid'], TemplateException)
        new_job_id = ret["id"]
        # Save template info
        if template_job:
            # Save template job
            TemplateJob.objects.create(
                job_id=new_job_id,
                template_code=template_job.template_code,
                username=submitter.username,
                json_body=template_job.json_body
            )
            # Save hooks
            hooks = JobComp.objects.filter(job=jobid).extra(
                {'notice': 'notice_type'}
            ).values(
                "url", "type", "method", "notice"
            )
            if hooks:
                with transaction.atomic():
                    save_notice_job(
                        hooks,
                        new_job_id
                    )
        # Get return job
        new_job = job_client.query_job(new_job_id)
        return Response({
            'id': new_job_id,
            'job_file': new_job['job_file']
        })


class NotifyJobView(InternalAPIView):
    JOB_STATE_MAPPING = {
        JobComp.STARTED: ['r', 'c'],
        JobComp.COMPLETED: ['c'],
    }

    def post(self, request):
        job_info = request.data
        with transaction.atomic():
            jobcomp_list = JobComp.objects.select_for_update().filter(
                job=job_info['id'],
                triggered=False
            )
            for jobcomp in jobcomp_list:
                if job_info['state'].lower() in \
                        self.JOB_STATE_MAPPING[jobcomp.type]:
                    task = getattr(
                        notice,
                        jobcomp.notice_type
                    )
                    task.delay(jobcomp_id=jobcomp.id, job_info=job_info)
                    jobcomp.triggered = True
                    jobcomp.save()
        return Response({})
