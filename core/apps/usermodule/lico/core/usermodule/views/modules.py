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
import os

from django.conf import settings
from django.db.transaction import atomic
from rest_framework.response import Response

from lico.core.contrib.exceptions import LicoInternalError
from lico.core.contrib.schema import json_schema_validate
from lico.core.contrib.views import APIView
from lico.core.template.models import Module

from ..exceptions import (
    UserModuleDeleteFailed, UserModuleException, UserModulePermissionDenied,
    UserModuleSubmitException,
)
from ..utils import (
    MODULE_FILE_DIR, EasyBuildUtils, EasyConfigParser, UserModuleJobHelper,
    get_fs_operator, get_private_module,
)

logger = logging.getLogger(__name__)


class ModuleListView(APIView):
    def get(self, request):
        filter_type = request.query_params.get("type", "")
        self.user = request.user

        if filter_type == "public":
            ret = self.get_public_modules()
        elif filter_type == "private":
            ret = self.get_private_modules()
        else:
            ret = self.get_public_modules()
            ret.extend(self.get_private_modules())

        return Response(ret)

    def get_public_modules(self):
        return [
            {
                "name": module.name,
                "items": [
                    {
                        "name": item.name,
                        "version": item.version,
                        "path": item.path,
                        "category": item.category,
                        "description": item.description,
                        "parents": item.parents_list,
                        "location": item.location,
                        "type": "public"
                    }
                    for item in module.items.iterator()
                ],
                "type": "public"
            }
            for module in Module.objects.order_by(
                "name"
            ).iterator()
        ]

    def get_private_modules(self):
        spider = os.path.join(settings.TEMPLATE.LMOD_DIR, "spider")
        modules = []
        try:
            modules = get_private_module(spider, self.user)
        except Exception as e:
            logger.exception(e)
            raise LicoInternalError
        return modules

    @json_schema_validate({
        "type": "object",
        "properties": {
            "fullname": {
                "type": "string",
                "minimum": 1,
            },
        },
        "required": [
            "fullname"
        ]
    }, is_get=True)
    def delete(self, request):
        module_name = request.query_params.get('fullname')

        eb_utils = EasyBuildUtils(request.user)
        modulefile_path = eb_utils.get_eb_module_file_path(module_name)
        software_path = eb_utils.get_eb_software_path(module_name)

        try:
            # delete software
            self.delete_path(request.user, software_path)

            # delete modelefile
            self.delete_path(request.user, modulefile_path)
        except UserModulePermissionDenied as e:
            logger.exception(e)
            raise UserModuleDeleteFailed
        except Exception as e:
            logger.exception(e)
            raise LicoInternalError

        # remove module dir when module dir empty
        try:
            if len(os.listdir(os.path.dirname(software_path))) == 0:
                self.delete_path(request.user, os.path.dirname(software_path))
        except Exception as e:
            logger.exception(e)
        try:
            if len(os.listdir(os.path.dirname(modulefile_path))) == 0:
                self.delete_path(
                    request.user, os.path.dirname(modulefile_path))
        except Exception as e:
            logger.exception(e)

        return Response({
            "status": "ok"
        })

    def delete_path(self, user, path):
        fopr = get_fs_operator(user)
        if not fopr.path_exists(path):
            return
        if not fopr.path_iswriteable(
                fopr.path_dirname(path), user.uid, user.gid):
            raise UserModulePermissionDenied
        if fopr.path_isfile(path):
            fopr.remove(path)
        elif fopr.path_isdir(path):
            fopr.rmtree(path)


class UserModuleSubmit(APIView):
    @json_schema_validate({
        "type": "object",
        "properties": {
            "easyconfig_path": {
                "type": "string",
                "minimum": 1
            },
            "job_queue": {
                "type": "string"
            },
            "template_id": {
                "type": "string"
            },
            "cores_per_node": {
                "type": "integer",
                "minimum": 1,
                "maximum": 999
            },
        },
        "required": [
            "easyconfig_path", "job_queue", "template_id"
        ]
    })
    @atomic
    def post(self, request):
        self.user = request.user
        data = request.data
        ret = self._request_job_proxy(data)
        return Response(ret)

    def _prepare_param(self, data):
        param = dict()
        param.update(data)
        eb_path = data["easyconfig_path"]
        param["job_name"] = os.path.splitext(os.path.basename(eb_path))[0]
        param["job_workspace"] = os.path.join(
            self.user.workspace, settings.USERMODULE.JOB_WORKSPACE
        )
        param["module_file_dir"] = MODULE_FILE_DIR

        return param

    def _request_job_proxy(self, data):
        helper = UserModuleJobHelper(self.user.username)
        param = self._prepare_param(data)
        try:
            ret = helper.submit_module_job(data["template_id"], param)
            job_id = ret['id']
            job = helper.query_job(job_id)
            ret.update(job)
            return ret
        except Exception:
            raise UserModuleSubmitException


class UserModuleSearch(APIView):
    def get(self, request, option):
        eb_utils = EasyBuildUtils(request.user)
        param = request.query_params.get('param', '')
        if option == "alnum":
            eb_configs = eb_utils.get_eb_configs(param=param)
        elif option == "name":
            eb_configs = eb_utils.get_eb_configs(param=param, is_alnum=False)
        else:
            raise NotImplementedError

        eb_data = list()
        for config in eb_configs:
            if not config or not config.endswith("eb"):
                continue
            if os.path.exists(config):
                try:
                    with open(config, 'r') as f:
                        module_info = EasyConfigParser(f.name, f.read()).\
                            parse()
                        if option == "name" and param.lower() \
                                not in module_info["name"].lower():
                            continue
                        eb_data.append(module_info)
                except Exception as e:
                    logger.exception(e)
                    raise UserModuleException

        return Response(eb_data)
