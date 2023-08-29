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

from lico.core.contrib.authentication import RemoteApiKeyAuthentication
from lico.core.contrib.schema import json_schema_validate
from lico.core.contrib.views import APIView

from ..cloudtools import get_operator
from ..exception import (
    ToolBusyNow, ToolInstanceDoesNotExist, ToolSettingsDoesNotExist,
)
from ..models import Project, Tool, ToolInstance, ToolSetting
from ..utils import (
    JobAndTemplateHelper, check_workspace, delete_project, get_instance_info,
    get_latest_tool_instance, get_modified_project, get_new_created_project,
    get_project, get_project_detail, get_share_url, get_tool,
    set_tool_settings, standard_path_format,
)

logger = logging.getLogger(__name__)


class OpenApiProjectList(APIView):
    authentication_classes = (
        RemoteApiKeyAuthentication,
    )

    def get(self, request):
        project_list = []
        for project in Project.objects.filter(
                username=request.user.username
        ).iterator():
            project_dict = project.as_dict(
                include=['name', 'workspace', 'environment']
            )
            project_dict.update({'project_id': project.id})
            project_list.append(project_dict)
        return Response(project_list)

    @json_schema_validate({
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "minLength": 1,
                "pattern": r"^\w+$"
            },
            "workspace": {
                "type": "string",
                "minLength": 1
            },
            "environment": {
                "type": "string",
                "minLength": 1
            }
        },
        "required": [
            "name", "workspace", "environment"
        ]
    })
    @atomic
    def post(self, request):
        data = request.data
        check_workspace(request.user, data['workspace'])
        request.data.update(
            {
                'workspace': standard_path_format(
                    request.user, data['workspace']
                ),
                'environment': standard_path_format(
                    request.user, data['environment']
                )
            }
        )
        project = get_new_created_project(request, is_openapi=True)
        project_dict = project.as_dict(
            include=['name', 'workspace', 'environment']
        )
        project_dict.update({'project_id': project.id})
        return Response(project_dict)


class OpenApiProjectDetail(APIView):
    authentication_classes = (
        RemoteApiKeyAuthentication,
    )

    def get(self, request, pk):
        project_dict = get_project_detail(pk, request.user.username)
        project_dict['project_id'] = project_dict.pop('id')
        for tool in project_dict.get("tools"):
            tool['tool_id'] = tool.pop("id")
            if tool.get("settings"):
                tool["settings"].pop("is_initialized")
                tool["settings"].update(
                    {"settings_id": tool["settings"].pop("id")}
                )
            if tool.get("instance"):
                tool["instance"].update(
                    {"instance_id": tool["instance"].pop("id")}
                )
        return Response(project_dict)

    @json_schema_validate({
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "minLength": 1,
                "pattern": r"^\w+$"
            }
        },
        "required": ["name"]
    })
    @atomic
    def put(self, request, pk):
        project = get_modified_project(request, pk, request.user.username)
        project_dict = project.as_dict(
            include=["name", "workspace", "environment"]
        )
        project_dict['project_id'] = project.id
        return Response(project_dict)

    def delete(self, request, pk):
        delete_project(request, pk, request.user.username)
        return Response()


class ToolList(APIView):
    authentication_classes = (
        RemoteApiKeyAuthentication,
    )

    def get(self, request):
        tools = []
        for tool in Tool.objects.all().iterator():
            tool_dict = tool.as_dict(
                include=[
                    "name", "code",
                    "job_template", "setting_params"
                ]
            )
            tool_dict.update(tool_id=tool.id)
            tools.append(tool_dict)
        return Response(tools)


class ToolSettings(APIView):
    authentication_classes = (
        RemoteApiKeyAuthentication,
    )

    @json_schema_validate({
        "type": "object",
        "properties": {
            "job_queue": {
                "type": "string",
                "minLength": 1,
                "pattern": r"^\S+$"
            },
            "cores_per_node": {
                "type": "integer",
                "minimum": 1,
                "maximum": 999
            },
            "gpu_per_node": {
                "type": "integer",
                "minimum": 0,
                "maximum": 99
            },
            "gpu_resource_name": {
                "type": "string"
            },
            "username": {
                "type": "string",
                "minLength": 1,
                "pattern": r"^\S+$"
            },
            "password": {
                "type": "string",
                "minLength": 1,
                "pattern": r"^\S+$"
            },
            "run_time": {
                "type": "string",
                "pattern": "^([0-9]+[d])?(\\s)*([0-9]+[h])?"
                           "(\\s)*([0-9]+[m])?(\\s)*$"
            },
            "check_timeout": {
                "type": "boolean"
            },
            "image_path": {
                "type": "string",
                "minLength": 1,
                "pattern": r"^\S+$"
            },
            "jupyter_cmd": {
                "type": "string"
            },
            "ram_size": {
                "type": "integer",
                "minimum": 1
            },
            "share_dir": {
                "type": "string"
            },
            "runtime_id": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "integer"
                }
            }
        },
        "required": [
            "job_queue", "cores_per_node", "password"
        ]
    })
    @atomic
    def post(self, request, project_id, tool_code):
        data = request.data
        project = get_project(project_id, request.user.username)
        tool = get_tool(tool_code)
        set_tool_settings(project, tool, data)

        return Response()


class ToolSubmit(APIView):
    authentication_classes = (
        RemoteApiKeyAuthentication,
    )

    @atomic
    def post(self, request, project_id, tool_code):
        user = request.user
        project = get_project(project_id, user.username)
        tool = get_tool(tool_code)
        if not self.check_instance_status(project, tool, user):
            raise ToolBusyNow('There is already a running instance')
        try:
            tool_setting = ToolSetting.objects.get(
                project=project, tool=tool
            )
        except ToolSetting.DoesNotExist as e:
            raise ToolSettingsDoesNotExist from e
        operator = get_operator(user, tool)
        instance = operator.create_instance(
            project=project, tool=tool,
            tool_setting=tool_setting
        )
        response = instance.as_dict(
            include=["template_job"]
        )
        response.update(job_id=instance.job)
        return Response(response)

    @staticmethod
    def check_instance_status(project, tool, user):
        latest_instance = get_latest_tool_instance(
            project=project, tool=tool
        )
        if latest_instance:
            job_id = latest_instance["job"]
            jat_helper = JobAndTemplateHelper(user.username)
            try:
                job = jat_helper.query_job(job_id)
            except Exception:
                logger.warning("job id not found: " + str(job_id))
                return True
            if job["status"] in [
                "running", "queueing", "cancelling", "suspending"
            ]:
                return False
        return True


class ToolInstanceInfo(APIView):
    authentication_classes = (
        RemoteApiKeyAuthentication,
    )

    @atomic
    def get(self, request, project_id, tool_code):
        user = request.user
        project = get_project(project_id, user.username)
        tool = get_tool(tool_code)
        operator = get_operator(user, tool)

        instance = ToolInstance.objects.filter(
            project=project, tool=tool
        )
        if not instance:
            raise ToolInstanceDoesNotExist('There is no running instance')
        instance = get_instance_info(
            user, instance.latest("create_time"), operator
        )
        instance_info = instance.as_dict(
            include=["template_job", "entrance_uri"]
        )
        instance_info.update(job_id=instance.job)

        return Response(instance_info)


class InstanceShareUrl(APIView):
    authentication_classes = (
        RemoteApiKeyAuthentication,
    )

    @atomic
    def post(self, request, project_id, tool_code):
        project = get_project(project_id, request.user.username)
        tool = get_tool(tool_code)
        share_url = get_share_url(project, tool)
        share_url.update(shareurl=share_url.pop("url"))
        return Response(share_url)
