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
from abc import ABCMeta, abstractmethod

from django.http import FileResponse
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from six import add_metaclass, raise_from

from lico.core.contrib.authentication import (
    RemoteApiKeyAuthentication, RemoteJWTInternalAuthentication,
    RemoteJWTWebAuthentication,
)
from lico.core.contrib.schema import json_schema_validate
from lico.core.contrib.views import APIView

from ..models import Template


class TemplatesDescView(APIView):
    @json_schema_validate({
        "type": "object",
        "properties": {
            "template_code": {
                "type": "array",
                "minItems": 0
            }
        },
        "required": [
            "template_code"
        ]
    })
    def post(self, request):
        template_code = request.data['template_code']
        templates = Template.objects.filter(code__in=template_code)
        data = templates.as_dict(
            include=['id', 'code', 'name', 'index', 'description']
        )
        return Response(data)


class TemplateListView(APIView):

    def get(self, request):
        return Response({
            'data': [
                {
                    'index': template.index,
                    'code': template.code,
                    'name': template.name,
                    'description': template.description,
                    'category': template.category,
                    'featureCode': template.feature_code,
                    'type': template.type,
                    'enable': template.enable,
                    'subTemplates': template.subtemplate
                    if template.subtemplate is None else json.loads(
                        template.subtemplate
                    ),
                    'params': template.params
                    if template.params is None else json.loads(
                        template.params
                    ),
                    # The following two fields are temporary
                    'logoUrl': '',
                    'template_file': ''
                }
                for template in Template.objects.filter(
                    display=True).iterator()
            ]
        })


@add_metaclass(ABCMeta)
class FileDownloadView(APIView):
    @staticmethod
    @abstractmethod
    def get_file_path(code):
        pass

    @staticmethod
    @abstractmethod
    def get_content_type():
        return 'application/json'

    def get(self, request, code):
        try:
            return FileResponse(
                open(self.get_file_path(code), 'rb'),
                content_type=self.get_content_type()
            )
        except IOError as e:
            raise_from(NotFound, e)


class TemplateDetailView(FileDownloadView):
    authentication_classes = (
        RemoteJWTWebAuthentication,
        RemoteJWTInternalAuthentication,
        RemoteApiKeyAuthentication
    )

    @staticmethod
    def get_file_path(code):
        return Template.objects.get(code=code).detail

    @staticmethod
    def get_content_type():
        return 'application/json'


class TemplateLogoView(FileDownloadView):
    permission_classes = ()

    @staticmethod
    def get_file_path(code):
        return Template.objects.get(code=code).logo

    @staticmethod
    def get_content_type():
        return 'image/jpeg'


class TemplateHelpView(FileDownloadView):
    permission_classes = ()

    @staticmethod
    def get_file_path(code, language):
        return Template.objects.get(
            code=code
        ).help_file_zh if language == 'zh' else Template.objects.get(
            code=code).help_file_en

    @staticmethod
    def get_content_type():
        return 'text/html'

    def get(self, request, code):
        language = request.GET.get('language', 'en')
        try:
            return FileResponse(
                open(self.get_file_path(code, language), 'rb'),
                content_type=self.get_content_type()
            )
        except IOError as e:
            raise_from(NotFound, e)


class TemplateResourceView(FileDownloadView):
    permission_classes = ()

    @staticmethod
    def get_file_path(code):
        return Template.objects.get(code=code).example

    @staticmethod
    def get_content_type():
        return 'application/zip'
