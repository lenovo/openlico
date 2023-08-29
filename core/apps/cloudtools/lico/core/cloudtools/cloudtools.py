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
import os
import time
import uuid
from abc import ABCMeta

from lico.core.contrib.base64 import encode_base64url

from .exception import CloudToolSubmitException
from .models import ToolInstance
from .utils import JobAndTemplateHelper, convert_myfolder, get_fs_operator


def get_operator(user, tool):
    return BaseCloudTools(user, tool.job_template)


class BaseCloudTools(metaclass=ABCMeta):
    def __init__(self, user, template_id):
        self.user = user
        self.template_id = template_id
        self.fopr = get_fs_operator(user)
        self.jat_helper = JobAndTemplateHelper(user.username)

    def _type_convert(self, param):
        default_value = param.get("defaultValue", "")
        if param.get("dataType") == "number":
            if param.get("floatLength", 0) == 0 and default_value:
                return int(default_value)
            elif param.get("floatLength", 0) > 0 and default_value:
                return round(float(default_value), param["floatLength"])
            else:
                return 0
        return default_value

    def base_parameters(self, project, tool_settings):
        # get parameters from template
        job_template = self.jat_helper.query_job_template(self.template_id)
        parameters = dict()
        for param in job_template['params']:
            parameters[param["id"]] = self._type_convert(param)
        parameters.update(
            job_name=self.template_id,
            job_uuid='le-{}'.format(uuid.uuid4()),
            job_workspace=self.get_job_workspace(project),
            persistent_dir=self.get_environment_dir(project),
            project_workspace=convert_myfolder(self.user, project.workspace)
        )
        return parameters

    def prepare_parameters(self, project, tool_settings):
        parameters = self.base_parameters(project, tool_settings)
        parameters.update(tool_settings.settings)
        # For compatibility with devtools, if existing_env exists,
        # both persistent_dir and job_workspace will change
        if tool_settings.existing_env:
            parameters.update(
                persistent_dir=convert_myfolder(
                    self.user, tool_settings.existing_env
                ),
                job_workspace=convert_myfolder(
                    self.user, project.workspace
                )
            )
        return parameters

    def get_cloudtools_dir(self, project):
        environment = os.path.join(project.environment, self.template_id)
        return convert_myfolder(self.user, environment)

    def get_environment_dir(self, project):
        environment = os.path.join(self.get_cloudtools_dir(project), "env")
        return environment

    def get_job_workspace(self, project):
        cloudtools_dir = self.get_cloudtools_dir(project)
        job_workspace = os.path.join(cloudtools_dir, "jobs")
        if not self.fopr.path_exists(job_workspace):
            self.fopr.makedirs(job_workspace)
            self.fopr.chown(cloudtools_dir, self.user.uid, self.user.gid)
            self.fopr.chown(job_workspace, self.user.uid, self.user.gid)
        return job_workspace

    def get_entrance_uri(self, job_info):
        entrance_uri = self.get_entrance_by_file(job_info)
        if entrance_uri:
            return entrance_uri
        else:
            return self.get_entrance_by_default(job_info)

    def get_entrance_by_file(self, job_info):
        template_job_dict = json.loads(
            job_info['template_job']['json_body']
        )
        entrance_uri_path = os.path.join(
            template_job_dict['parameters']['job_workspace'],
            'entrance_uri.json')
        for _ in range(10):
            if self.fopr.path_exists(entrance_uri_path):
                with self.fopr.open_file(entrance_uri_path, 'r') as f:
                    data = json.load(f.file_handle)
                    entrance_uri = data.get("entrance_uri").strip()
                    if entrance_uri:
                        return entrance_uri
            time.sleep(1)
        return ''

    def get_entrance_by_default(self, job_info):
        job_dict = job_info["job"]
        template_job_dict = json.loads(
            job_info["template_job"]['json_body']
        )
        if self.queue_host(job_dict):
            uuid = template_job_dict['parameters']['job_uuid']
            queue_host = self.queue_host(job_dict)
            return "/dev/{}/{}/{}/".format(self.template_id, queue_host, uuid)
        return ''

    def _request_job_proxy(self, user, parameters):
        try:
            ret = self.jat_helper.submit_template_job(
                self.template_id, parameters
            )
            job_id = ret['id']
            job = self.jat_helper.query_job(job_id)
            template_job = self.jat_helper.query_template_job(job_id)
            return dict(
                job=job,
                template_job=template_job
            )
        except Exception as e:
            try:
                error_info = json.loads(str(e))
                if isinstance(error_info, dict):
                    CloudToolSubmitException.errid = error_info.get("errid")
                    CloudToolSubmitException.message = error_info.get("msg")
            finally:
                raise CloudToolSubmitException from e

    def create_instance(self, project, tool, tool_setting):
        parameters = self.prepare_parameters(project, tool_setting)
        job_info = self._request_job_proxy(self.user, parameters)

        return ToolInstance.objects.create(
            project=project, tool=tool,
            template_job=job_info["template_job"]['id'],
            job=job_info["job"]['id']
        )

    def queue_host(self, item):
        if item['status'] == "running":
            import socket
            ports = item['ports']
            if ports:
                return encode_base64url(
                    "{}:{}".format(
                        socket.gethostbyname(item['exechosts'].split("*")[0]),
                        ports['port0']
                    ).encode()
                ).decode()
        else:
            return ''
