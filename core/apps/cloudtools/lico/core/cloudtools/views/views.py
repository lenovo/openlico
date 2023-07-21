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
from rest_framework.views import APIView as BaseAPIView

from lico.core.contrib.schema import json_schema_validate
from lico.core.contrib.views import APIView

from ..cloudtools import get_operator
from ..models import Project, Tool, ToolInstance, ToolSetting, ToolSharing
from ..utils import (
    delete_project, get_instance_info, get_modified_project,
    get_new_created_project, get_project_detail, get_share_url,
    set_tool_settings,
)

logger = logging.getLogger(__name__)


class ProjectList(APIView):

    def get(self, request):
        return Response(
            [
                project.as_dict(include=['id', 'name'])
                for project in Project.objects.filter(
                    username=request.user.username
                ).iterator()
            ]
        )

    @json_schema_validate({
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "minLength": 1
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
        project = get_new_created_project(request)
        return Response(
            project.as_dict(
                include=['id', 'name']
            )
        )


class ProjectDetail(APIView):

    def get(self, request, pk):
        return Response(get_project_detail(pk))

    @json_schema_validate({
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "minLength": 1
            }
        },
        "required": [
            "name"
        ]
    })
    @atomic
    def put(self, request, pk):
        return Response(
            get_modified_project(request, pk).as_dict(
                include=["id", "name"]
            )
        )

    def delete(self, request, pk):
        delete_project(request, pk)
        return Response()


class SettingList(APIView):

    @json_schema_validate({
        "type": "object",
        "properties": {
            "project_id": {
                "type": "integer",
                "minimum": 1,
            },
            "tool_id": {
                "type": "integer",
                "minimum": 1
            },
            "job_queue": {
                "type": "string",
                "minLength": 1
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
            "password": {
                "type": "string",
            },
            "username": {
                "type": "string",
                "minLength": 1,
                "pattern": r"^\S+$"
            },
            "run_time": {
                "type": "string",
                "pattern": "^([0-9]+[d])?(\\s)*([0-9]+[h])?"
                           "(\\s)*([0-9]+[m])?(\\s)*$"
            },
            "language": {
                "type": "string",
                "enum": ["py37", "py38"]
            },
        },
        "required": [
            "project_id", "tool_id"
        ]
    })
    @atomic
    def post(self, request):
        data = request.data
        project = Project.objects.get(id=data.pop("project_id"))
        tool = Tool.objects.get(id=data.pop("tool_id"))
        tool_setting = set_tool_settings(project, tool, data)
        return Response(tool_setting.as_dict(
            include=[
                "id", "settings", "is_initialized", "tool", "project"
            ],
            inspect_related=True,
            related_field_options=dict(
                tool=dict(include=["id", "name", "code"]),
                project=dict(include=["id", "name"])
            )
        ))


class SettingDetail(APIView):

    def get(self, request, pk):
        return ToolSetting.objects.get(id=pk).as_dict(
            include=["id", "settings", "is_initialized", "tool", "project"],
            inspect_related=True,
            related_field_options=dict(
                tool=dict(include=["id", "name", "code"]),
                project=dict(include=["id", "name"])
            )
        )

    @json_schema_validate({
        "type": "object",
        "properties": {
            "job_queue": {
                "type": "string",
                "minLength": 1
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
            "password": {
                "type": "string",
            },
            "username": {
                "type": "string",
                "minLength": 1,
                "pattern": r"^\S+$"
            },
            "run_time": {
                "type": "string",
                "pattern": "^([0-9]+[d])?(\\s)*([0-9]+[h])?"
                           "(\\s)*([0-9]+[m])?(\\s)*$"
            }
        }
    })
    @atomic
    def put(self, request, pk):
        tool_setting = ToolSetting.objects.get(id=pk)
        settings = tool_setting.settings
        settings.update(request.data)
        tool_setting.is_initialized = True
        tool_setting.settings = settings
        tool_setting.save()
        return Response(
            tool_setting.as_dict(
                include=["id", "settings", "is_initialized"]
            )
        )


class CloudToolSubmit(APIView):

    @json_schema_validate({
        "type": "object",
        "properties": {
            "project_id": {
                "type": "integer",
                "minimum": 1,
            },
            "tool_id": {
                "type": "integer",
                "minimum": 1
            }
        },
        "required": [
            "project_id", "tool_id"
        ]
    })
    @atomic
    def post(self, request):
        user = request.user
        tool = Tool.objects.get(id=request.data["tool_id"])
        project = Project.objects.get(id=request.data["project_id"])
        tool_settings = ToolSetting.objects.filter(
            project=project, tool=tool
        ).first()
        operator = get_operator(user, tool)
        instance = operator.create_instance(
            project=project, tool=tool,
            tool_setting=tool_settings
        )
        return Response(instance.as_dict(
            include=[
                "id", "job", "template_job",
                "tool", "project"
            ],
            inspect_related=True,
            related_field_options=dict(
                tool=dict(include=["id", "name", "code"]),
                project=dict(include=["id", "name"])
            )
        ))


class InstanceDetail(APIView):

    @atomic
    def get(self, request, pk):
        user = request.user
        instance = ToolInstance.objects.get(id=pk)
        tool = Tool.objects.get(id=instance.tool.id)
        operator = get_operator(user, tool)
        instance = get_instance_info(user, instance, operator)
        return Response(
            instance.as_dict(
                include=[
                    "id", "job", "template_job",
                    "entrance_uri", "tool", "project"
                ],
                inspect_related=True,
                related_field_options=dict(
                    tool=dict(include=["id", "name", "code"]),
                    project=dict(include=["id", "name"])
                )
            )
        )


class ShareUrl(APIView):

    @json_schema_validate({
        "type": "object",
        "properties": {
            "project_id": {
                "type": "integer",
                "minimum": 1,
            },
            "tool_id": {
                "type": "integer",
                "minimum": 1
            }
        },
        "required": [
            "project_id", "tool_id"
        ]
    })
    @atomic
    def post(self, request):
        project = Project.objects.get(id=request.data['project_id'])
        tool = Tool.objects.get(id=request.data['tool_id'])
        share_url = get_share_url(project, tool)
        return Response(share_url)


class ShareView(BaseAPIView):

    @json_schema_validate({
        "type": "object",
        "properties": {
            "uuid": {
                "type": "string",
                "minLength": 1
            }
        },
        "required": [
            "uuid"
        ]
    }, is_get=True)
    @atomic
    def get(self, request):
        sharing = ToolSharing.objects.filter(
            sharing_uuid=request.query_params["uuid"]
        ).first()
        if sharing:
            tool_id = sharing.tool.id
            project_id = sharing.project.id
            try:
                instance = ToolInstance.objects.filter(
                    tool__id=int(tool_id), project__id=int(project_id)
                ).latest('create_time').as_dict()
                return Response({
                    "redirect_url": ''
                    if instance['entrance_uri'] is None
                    else instance['entrance_uri'],
                    "job_template": sharing.tool.job_template
                })
            except ToolInstance.DoesNotExist:
                logger.warning("ToolInstance does not exist", exc_info=True)

        return Response({
            "redirect_url": '',
            "job_template": ''
        })
