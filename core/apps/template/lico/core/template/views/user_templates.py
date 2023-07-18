# -*-coding:utf-8 -*-
# Copyright 2018-present Lenovo
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

import base64
import imghdr
import json
import logging
import os
import tempfile
import time

import pkg_resources
from django.conf import settings
from django.db.models import Q
from django.http import StreamingHttpResponse
from rest_framework import status
from rest_framework.response import Response

from lico.core.contrib.schema import json_schema_validate
from lico.core.contrib.views import APIView

from ..exceptions import (
    InvalidLogoException, LogoSizeTooLargeException, SubmitJobException,
    UserTemplateExistsException,
)
from ..helpers.fs_operator_helper import get_fs_operator
from ..models import UserTemplate
from ..utils.template_utils import export_template_file, import_template_file

logger = logging.getLogger(__name__)


class UserTemplateDetailView(APIView):
    """
    Retrieve, update or delete a UserTemplate instance.
    """

    def get(self, request, pk):
        job_template = UserTemplate.objects.filter(
            Q(username=request.user.username) | Q(type='public')
        ).get(pk=pk)
        data = job_template.as_dict()
        data['workspace'] = request.user.workspace
        return Response(data)

    @json_schema_validate({
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "logo": {"type": "string"},
            "parameters_json": {"type": "string"},
            "template_file": {"type": "string"},
            "desc": {"type": "string"},
            "index": {
                "type": "integer",
                "minimum": 1,
                "maximum": 99999
            }
        },
        "required": ["name", "logo", "parameters_json",
                     "template_file", "desc", "index"]
    })
    def put(self, request, pk):
        workspace = request.user.workspace
        data = validate_job_template_params(
            request.data, workspace, request.user, pk
        )
        job_template = UserTemplate.objects.filter(
            id=pk,
            username=request.user.username
        )
        job_template_key_list = [i.name for i in UserTemplate._meta.fields]
        new_job_template_dict = {
            k: v for k, v in data.items() if k in job_template_key_list
            }
        if not new_job_template_dict['logo']:
            new_job_template_dict.pop('logo')

        job_template.update(**new_job_template_dict)
        job_template_updated = UserTemplate.objects.get(id=pk)
        return Response(job_template_updated.as_dict())

    def delete(self, request, pk):
        job_template = UserTemplate.objects.exclude(
            type='public').get(
            pk=pk, username=request.user.username)
        job_template.delete()
        return Response(job_template.as_dict(),
                        status=status.HTTP_204_NO_CONTENT)


class UserTemplateListView(APIView):
    """
    List all UserTemplates, or create a new UserTemplate.
    """

    def get(self, request):
        job_templates = UserTemplate.objects.filter(
            username=request.user.username).order_by('-create_time')
        serializer_data = [obj.as_dict() for obj in job_templates]
        public_templates = UserTemplate.objects.filter(
            type='public').exclude(
            username=request.user.username).order_by('-create_time')
        for template in public_templates:
            serializer_data.append(template.as_dict())
        result = []
        for data in serializer_data:
            data["logo"] = ""
            data["parameters_json"] = ""
            data["template_file"] = ""
            result.append(data)
        return Response({'data': result})

    @json_schema_validate({
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "logo": {"type": "string"},
            "parameters_json": {"type": "string"},
            "template_file": {"type": "string"},
            "category": {"type": "string"},
            "desc": {"type": "string"},
            "index": {
                "type": "integer",
                "minimum": 1,
                "maximum": 99999
            }
        },
        "required": ["name", "logo", "parameters_json",
                     "template_file", "desc", "category", "index"]
    })
    def post(self, request):
        workspace = request.user.workspace
        data = validate_job_template_params(
            request.data, workspace, request.user
        )
        if not data:
            raise SubmitJobException
        data['username'] = request.user.username
        data['scheduler'] = settings.LICO.SCHEDULER
        data['type'] = 'private'
        job_template_key_list = [i.name for i in UserTemplate._meta.fields]
        new_job_template_dict = {
            k: v for k, v in data.items() if k in job_template_key_list
            }

        usertemplate_created = UserTemplate.objects.create(
            **new_job_template_dict)
        return Response(
            usertemplate_created.as_dict(),
            status=status.HTTP_201_CREATED)


class UserTemplatePublishView(APIView):
    def post(self, request, pk):
        job_template = UserTemplate.objects.exclude(
            type='public').get(
            pk=pk, username=request.user.username)
        job_template.type = 'public'
        job_template.save()
        return Response(job_template.as_dict())


class UserTemplateUnpublishView(APIView):
    def post(self, request, pk):
        job_template = UserTemplate.objects.exclude(
            type='private').get(pk=pk, username=request.user.username)
        job_template.type = 'private'
        job_template.save()
        return Response(job_template.as_dict())


def validate_job_template_params(  # noqa:C901
        data, workspace, user, pk=None):
    if pk is None:
        if UserTemplate.objects.filter(name=data['name']):
            raise UserTemplateExistsException
    else:
        objs = UserTemplate.objects.filter(name=data['name']).exclude(id=pk)
        if objs:
            raise UserTemplateExistsException
    if len(data['logo']) > 0:
        if data['logo'].startswith('data:image/jpeg;base64,'):
            # After base64 the length can be increased 1.3 at most.
            if len(data['logo']) > 100 * 1024 * 1.3:
                raise LogoSizeTooLargeException
        else:
            logo_image_filename = data['logo']
            from ..utils.common import convert_myfolder
            op = get_fs_operator(user=user)
            logo_image_filename = convert_myfolder(
                op, user, logo_image_filename)
            _, file_name = os.path.split(logo_image_filename)
            tmp_img_file = os.path.join(tempfile.gettempdir(), file_name)
            op.download_file(logo_image_filename, tmp_img_file)
            if not imghdr.what(tmp_img_file):
                raise InvalidLogoException
            # not larger than 100KB( Original: 2M--2 * (1024 ** 2))
            if os.path.getsize(tmp_img_file) > 100 * 1024:
                raise LogoSizeTooLargeException
            # Encode pictures
            with open(tmp_img_file, 'rb') as f:
                data['logo'] = 'data:image/jpeg;base64,' \
                               + base64.b64encode(f.read()).decode()
            os.remove(tmp_img_file)

    # set default run time if no value was provided
    params = json.loads(data["parameters_json"])
    for p in params:
        if p["id"] == "run_time" and not p["defaultValue"]:
            p["defaultValue"] = settings.TEMPLATE.DEFAULT_RUN_TIME
    data["parameters_json"] = json.dumps(params)
    return data


class UserTemplateExportView(APIView):
    def get(self, request, pk):
        import uuid
        try:
            template = UserTemplate.objects.get(
                pk=pk,
                username=request.user.username
            )
        except UserTemplate.DoesNotExist:
            logger.exception("Job template %s is not exist", pk)
            raise

        template_data = template.as_dict()
        export_dict = {
            'version': pkg_resources.get_distribution(
                'lico-core-template').version,
            'MagicNumber': str(uuid.uuid1()),
            'exporter': request.user.username,
            'export_time': str(int(time.time())),
            # License doesn't contain customer name.
            # Remove source from LiCO 6.0.
            'source': '',
            'scheduler': template_data['scheduler'],
            'index': template_data['index'],
            'name': template_data['name'],
            'category': template_data['category'],
            'logo': template_data['logo'],
            'desc': template_data['desc'],
            'parameters_json': template_data['parameters_json'],
            'template_file': template_data['template_file']
        }
        file_name = export_dict['name'] + "_" + str(int(time.time())) + '.ljt'

        from io import BytesIO

        str_data = export_template_file(export_dict)

        response = StreamingHttpResponse(BytesIO(str_data.encode()))
        response['Content-Type'] = 'application/octet-stream'
        response['Content-Disposition'] = \
            'attachement;filename="{0}"'.format(file_name)

        return response


class UserTemplateImportView(APIView):
    def post(self, request):
        data = request.data
        # check template_name
        if UserTemplate.objects.filter(name=data['name']):
            raise UserTemplateExistsException
        job_file = data['upload']
        import_dict = import_template_file(job_file)
        UserTemplate.objects.create(
            name=data["name"],
            logo=import_dict["logo"],
            desc=import_dict["desc"],
            parameters_json=import_dict["parameters_json"],
            index=import_dict.get("index", 99999),
            category=import_dict.get("category", "General"),
            template_file=import_dict["template_file"],
            scheduler=import_dict["scheduler"],
            type="private",
            username=request.user.username
        )
        return Response()


class UserTemplateLogoView(APIView):
    permission_classes = ()

    def get(self, request, pk):
        from django.http import HttpResponse
        logo = UserTemplate.objects.get(id=pk).logo
        return HttpResponse(
            base64.b64decode(logo.split(',')[1]),
            content_type='image/jpeg',
            )
