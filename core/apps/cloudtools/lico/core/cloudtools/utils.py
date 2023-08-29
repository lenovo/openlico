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
import uuid

from django.db.utils import IntegrityError
from rest_framework import status
from rest_framework.exceptions import PermissionDenied

from lico.client.contrib.exception import NotFound
from lico.core.contrib.client import Client
from lico.core.contrib.exceptions import LicoError

from .exception import (
    EnvironmentAlreadyUsed, PathFormatException, ProjectAlreadyExist,
    ProjectBusyNow, ProjectDoesNotExist, ProjectEnvDeleteException,
    SettingAlreadyExist, ToolDoesNotExist, UnableDefaultProject,
)
from .models import Project, Tool, ToolInstance, ToolSetting, ToolSharing

salt_len = 12

logger = logging.getLogger(__name__)


def get_fs_operator(user):
    from lico.core.contrib.client import Client
    return Client().filesystem_client(user=user)


def get_new_created_project(request, is_openapi=False):
    data = request.data
    if not check_environment(
            request, data["environment"], is_openapi
    ):
        raise EnvironmentAlreadyUsed
    try:
        project = Project.objects.create(
            name=data['name'],
            workspace=data['workspace'],
            username=request.user.username,
            environment=data["environment"]
        )
    except IntegrityError as e:
        raise ProjectAlreadyExist from e
    return project


def check_environment(request, env, is_openapi):
    environment = convert_myfolder(
        request.user, env
    )
    if Project.objects.filter(
            username=request.user.username, environment=env
    ).exists():
        return False
    file_operator = get_fs_operator(request.user)
    if file_operator.path_isdir(environment):
        if file_operator.listdir(environment):
            return False
    elif file_operator.path_isfile(environment):
        if is_openapi:
            raise PathFormatException(f"{env} is invalid")
        return False
    else:
        if is_openapi:
            raise PathFormatException(f"{env} is invalid")
        file_operator.mkdir(environment)
        file_operator.chown(
            environment, request.user.uid, request.user.gid
        )
    return True


def convert_myfolder(user, origin_path):
    from os import path
    if not origin_path.startswith('MyFolder'):
        return origin_path
    return path.realpath(
        path.join(
            user.workspace,
            path.relpath(origin_path, start='MyFolder')
        )
    )


def check_workspace(user, origin_path):
    environment = convert_myfolder(user, origin_path)
    file_operator = get_fs_operator(user)
    if not file_operator.path_isdir(environment):
        raise PathFormatException(f"{origin_path} is invalid")


def standard_path_format(user, origin_path):
    if not origin_path.startswith('MyFolder') and \
            not origin_path.startswith(user.workspace):
        raise PathFormatException(f"{origin_path} format is invalid")
    if origin_path.startswith('MyFolder'):
        return origin_path
    return origin_path.replace(user.workspace, 'MyFolder', 1)


def get_project_detail(pk, username=None):
    project = get_project(pk, username)
    tools = []
    for tool in Tool.objects.all().iterator():
        tool_dict = tool.as_dict(
            include=[
                "id", "name", "code",
                "job_template", "setting_params"
            ]
        )
        tool_dict.update(
            settings=get_tool_setting(
                project=project, tool=tool
            ),
            instance=get_latest_tool_instance(
                project=project, tool=tool
            )
        )
        tools.append(tool_dict)
    project_dict = project.as_dict(
        include=[
            'id', 'name', 'workspace',
            'environment', 'settings'
        ]
    )
    project_dict.update(tools=tools)
    return project_dict


def get_project(project_id, username):
    try:
        project = Project.objects.get(id=project_id)
    except Project.DoesNotExist as e:
        raise ProjectDoesNotExist from e
    if username:
        if project.username != username:
            raise PermissionDenied
    return project


def get_tool_setting(project, tool):
    tool_setting = {}
    try:
        tool_setting = ToolSetting.objects.filter(
            tool=tool, project=project
        ).latest(
            'create_time'
        ).as_dict(include=['id', 'settings', "is_initialized"])
    except ToolSetting.DoesNotExist:
        logger.warning("ToolSetting not found.")
    return tool_setting


def get_latest_tool_instance(project, tool):
    tool_instance = {}
    try:
        tool_instance = ToolInstance.objects.filter(
            tool=tool, project=project
        ).latest('create_time').as_dict(
            include=['id', 'job', 'template_job', 'entrance_uri']
        )
    except ToolInstance.DoesNotExist:
        logger.warning("ToolInstance not found.")
    return tool_instance


def get_modified_project(request, pk, username=None):
    project = get_project(pk, username)
    if project.name == "default":
        raise UnableDefaultProject
    if not check_project_status(request.user.username, project):
        raise ProjectBusyNow
    try:
        new_name = request.data["name"]
        project.name = new_name
        project.save()
    except IntegrityError as e:
        raise ProjectAlreadyExist from e
    return project


def delete_project(request, pk, username=None):
    project = get_project(pk, username)
    confirm = request.data.get('delete_completely', False)
    if project.name == "default":
        raise UnableDefaultProject
    if not check_project_status(request.user.username, project):
        raise ProjectBusyNow
    if confirm:
        delete_env(request.user, project)
    project.delete()


def check_project_status(username, project):
    for tool in Tool.objects.all().iterator():
        latest_instance = get_latest_tool_instance(
            project=project, tool=tool
        )
        if latest_instance:
            job_id = latest_instance["job"]
            jat_helper = JobAndTemplateHelper(username)
            try:
                job = jat_helper.query_job(job_id)
                if job["status"] in [
                    "running", "queueing", "cancelling", "suspending"
                ]:
                    return False
            except Exception:
                logger.warning("job id not found: " + str(job_id))
    return True


def delete_env(user, project):
    environment = convert_myfolder(
        user,
        project.environment
    )
    file_operator = get_fs_operator(user)
    if file_operator.path_isdir(environment):
        try:
            file_operator.rmtree(environment)
        except Exception:
            raise ProjectEnvDeleteException


def get_tool(tool_code):
    try:
        tool = Tool.objects.get(code=tool_code)
    except Tool.DoesNotExist as e:
        raise ToolDoesNotExist from e
    return tool


def set_tool_settings(project, tool, data):
    try:
        tool_setting, _ = ToolSetting.objects.select_for_update(). \
            update_or_create(
            project=project, tool=tool, defaults={"settings": data}
        )
    except IntegrityError as e:
        raise SettingAlreadyExist from e
    return tool_setting


def get_instance_info(user, instance, operator):
    jat_helper = JobAndTemplateHelper(user.username)
    job = jat_helper.query_job(instance.job)

    template_job = jat_helper.query_template_job(instance.job)
    job_info = dict(
        job=job,
        template_job=template_job
    )
    if not instance.entrance_uri:
        entrance_uri = operator.get_entrance_uri(job_info)
        if entrance_uri:
            instance.entrance_uri = entrance_uri
            instance.save()
    return instance


def get_share_url(project, tool):
    sharing = ToolSharing.objects.filter(
        project__id=project.id, tool__id=tool.id
    ).first()
    if sharing:
        url_uuid = sharing.sharing_uuid
    else:
        url_uuid = f'{uuid.uuid4()}-{project.id}-{tool.id}'
        ToolSharing.objects.create(
            project=project, tool=tool, sharing_uuid=url_uuid
        )
    return {"url": f'/cloudtools/{url_uuid}'}


class JobException(LicoError):
    status_code = status.HTTP_400_BAD_REQUEST
    message = 'Job operation error.'
    errid = 7000

    def __init__(self, msg=None):
        super(JobException, self).__init__(msg)
        self.detail = {
            'msg': (msg or self.message),
            'errid': str(self.errid)
        }


class JobAndTemplateHelper(object):
    def __init__(self, username=None):
        if username is None:
            self._job_client = Client().job_client()
            self._template_client = Client().template_client()
        else:
            self._job_client = Client().job_client(username=username)
            self._template_client = Client().template_client(username=username)

    def query_job(self, job_id):
        try:
            job = self._job_client.query_job(job_id)
            job['status'] = self.get_job_status(job)
            job['exechosts'] = self.get_job_exechosts(job)
            job['ports'] = self.get_ports(job)
            return job
        except NotFound:
            raise JobException("job id not found: " + str(job_id))

    def query_job_list(self, job_id_list, submitter):
        job_list = self._job_client.job_list(job_id_list, submitter)
        job_list_new = []
        for job in job_list:
            job['cpus'] = self.get_cpu_cores_from_tres(job["tres"])
            job['gpus'] = self.get_gpu_cores_from_tres(job["tres"])
            job['status'] = self.get_job_status(job)
            job['exechosts'] = self.get_job_exechosts(job)
            job_list_new.append(job)
        return job_list_new

    def get_job_status(self, job):
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

    def get_job_exechosts(self, job):
        exechosts = []
        for running in job['job_running']:
            hosts = running['hosts']
            cpu_cores = self.get_cpu_cores_from_tres(
                running['per_host_tres'])
            exechosts.append(hosts + '*' + str(cpu_cores))
        return ','.join(exechosts)

    def get_cpu_cores_from_tres(self, tres):
        res_list = tres.split(',')
        for res in res_list:
            vals = res.split(':')
            if vals[0] == 'C':
                # Currently lico only support
                # int nodes.
                return int(float(vals[1]))

    def get_gpu_cores_from_tres(self, tres):
        res_list = tres.split(',')
        for res in res_list:
            vals = res.split(':')
            if vals[0] == 'G/gpu':
                # Currently lico only support
                # int nodes.
                return int(float(vals[1]))
        return 0

    def get_ports(self, job):
        ports = dict()
        port_idx = 0
        for csres in job['job_csres']:
            if csres['csres_code'] == 'port':
                port = int(csres['csres_value'])
                ports['port' + str(port_idx)] = port
                port_idx += 1
        return ports

    def get_all_queues(self):
        return ['compute']

    def submit_template_job(self, template_id, template_param_vals):
        template_job = self._template_client.submit_template_job(
            template_id, template_param_vals)
        return template_job

    def query_current_jobs(self):
        running_jobs = self._job_client.query_recent_jobs(end_time_offset=300)
        return running_jobs

    def get_job_template_id(self, job_id):
        try:
            template_job = self._template_client.query_template_job(job_id)
            return template_job['template_code']
        except NotFound:
            logger.info('Can not found template code of job: ' + str(job_id))
            return ''

    def cancel_job(self, job_id):
        self._job_client.cancel_job(job_id)

    def query_template_job(self, job_id):
        try:
            template_job = self._template_client.query_template_job(job_id)
            return template_job
        except NotFound:
            raise JobException("job id not found template: " + str(job_id))

    def query_job_template(self, template_code):
        try:
            job_template = self._template_client.get_job_template(
                template_code)
            return job_template
        except NotFound:
            raise JobException(
                "Can not found job template of code: " + str(template_code))
