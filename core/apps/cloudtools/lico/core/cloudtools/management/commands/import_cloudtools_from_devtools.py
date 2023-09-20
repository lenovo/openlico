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
import json
import os
from collections import defaultdict

from django.conf import settings
from django.core.management import BaseCommand
from django.db.transaction import atomic

from lico.core.cloudtools.models import (
    Project, Tool, ToolInstance, ToolSetting,
)
from lico.core.contrib.client import Client
from lico.core.devtools.models import Devtools


def print_green(string):
    print(f'\033[92m{string}\033[0m')


def print_red(string):
    print(f'\033[31m{string}\033[0m')


class Command(BaseCommand):
    help = 'import cloudtools from devtools'

    def handle(self, *args, **options):
        try:
            tool = self.get_cloudtools_tool()
        except Exception as e:
            print_red('The cloudtools named Jupyter does not exist.')
            raise SystemExit(-1) from e
        system_containers = self.get_all_system_containers()
        self.import_cloudtools(tool, system_containers)

    # flake8: noqa: C901
    @atomic
    def import_cloudtools(self, tool, system_containers):
        not_exists_user = set()
        def_workspace = defaultdict(list)
        default_environ = defaultdict(list)
        default_dict = defaultdict(int)
        template_client = Client().template_client()
        for devtool in Devtools.objects.all().iterator():
            changed_uuid = self.get_changed_uuid(devtool.uuid)
            if changed_uuid:
                try:
                    self.check_user_exists(
                        devtool.username, not_exists_user
                    )
                except Exception as e:
                    print_red(f'devtool with id {devtool.id}: {e}')
                    continue
                try:
                    template_job_info = self.get_template_job_info(
                        template_client, devtool.job
                    )
                    parameters = self.get_parameters(template_job_info)
                    conda_env = self.get_conda_env(
                        default_environ, parameters, devtool.username
                    )
                    workspace = self.get_job_workspace(
                        def_workspace, parameters, devtool.username
                    )
                except Exception as e:
                    print_red(f'devtool with id {devtool.id}: {e}')
                    devtool.uuid = changed_uuid
                    devtool.save()
                    continue
                try:
                    container = self.get_container_image(
                        parameters, system_containers
                    )
                except Exception as e:
                    print_red(f'devtool with id {devtool.id}: {e}')
                    continue
                try:
                    project = Project.objects.create(
                        name=self.get_project_name(
                            devtool.username, default_dict
                        ),
                        username=devtool.username,
                        workspace=workspace,
                        environment=os.path.join(workspace, '.lico_env')
                    )
                    ToolSetting.objects.create(
                        tool=tool, project=project,
                        settings=self.prepare_tool_instance_settings(
                            parameters, container
                        ),
                        existing_env=conda_env,
                        is_initialized=False
                    )
                    ToolInstance.objects.create(
                        tool=tool, project=project,
                        job=template_job_info["job_id"],
                        template_job=template_job_info["id"]
                    )
                    devtool.uuid = changed_uuid
                    devtool.save()
                    print_green(
                        f'devtool with id {devtool.id}: import success'
                    )
                except Exception:
                    print_red(f'devtools with id {devtool.id} is invalid')
                    devtool.uuid = changed_uuid
                    devtool.save()
                    continue

    @staticmethod
    def get_changed_uuid(uuid):
        if not uuid.endswith('-lico-discarded'):
            return f'{uuid}-lico-discarded'

    @staticmethod
    def get_job_info(client, job_id):
        try:
            job_info = client.query_job(job_id)
            return job_info
        except Exception:
            raise Exception("job instance does not exist")

    @staticmethod
    def get_template_job_info(client, job_id):
        try:
            template_job_info = client.query_template_job(job_id)
            return template_job_info
        except Exception:
            raise Exception("job instance does not exist")

    @staticmethod
    def get_parameters(template_job_info):
        json_body = template_job_info['json_body']
        parameters = json.loads(json_body).get(
            'parameters', {}
        )
        return parameters

    @staticmethod
    def get_conda_env(default_environ, parameters, username):
        conda_env = parameters.get('job_workspace') if parameters.get(
            'language', ''
        ) == 'custom' else parameters.get('conda_env')
        if conda_env is None:
            raise Exception("Conda environment address cannot be empty")
        if conda_env in default_environ[username]:
            raise Exception("Conda environment address duplication")
        default_environ[username].append(conda_env)
        return conda_env

    @staticmethod
    def get_job_workspace(default_workspace, parameters, username):
        workspace = parameters.get('job_workspace')
        if workspace is None:
            raise Exception("Job workspace address cannot be empty")
        if workspace in default_workspace[username]:
            raise Exception("Job workspace address duplication")
        default_workspace[username].append(workspace)
        return workspace

    @staticmethod
    def get_cloudtools_tool(code="jupyter"):
        try:
            tool = Tool.objects.get(code=code)
            return tool
        except Tool.DoesNotExist:
            raise

    def get_container_image(self, parameters, system_containers):
        language = parameters.get('language')
        if language in [
            "py36", "py37", "custom",
            "intel_oneapi_pytorch", "intel_oneapi_tensorflow2"
        ]:
            image_path = self.get_image_path(
                language, parameters, system_containers
            )
            if image_path:
                if settings.LICO.ARCH == 'host':
                    if os.path.exists(image_path):
                        return image_path
                else:
                    return image_path
        raise Exception("Unable to find system image")

    @staticmethod
    def get_image_path(language, parameters, system_containers):
        gpu_per_node = parameters.get('gpu_per_node', 0)
        image_path = ''
        if language == "custom":
            image_path = parameters.get("image_path", '')
        if language == "intel_oneapi_pytorch":
            image_path = system_containers["intel_oneapi_pytorch"]
        if language == "intel_oneapi_tensorflow2":
            image_path = system_containers["intel_oneapi_tensorflow2"]
        if language == "py36" and gpu_per_node:
            image_path = system_containers["py36_gpu"]
        if language == "py37" and gpu_per_node:
            image_path = system_containers["py37_gpu"]
        if language == "py36":
            image_path = system_containers["py36_cpu"]
        if language == "py37":
            image_path = system_containers["py37_cpu"]
        return image_path

    def get_all_system_containers(self):
        return {
            "py36_cpu": self.get_one_system_image('py36', 'cpu'),
            "py36_gpu": self.get_one_system_image('py36', 'gpu'),
            "py37_cpu": self.get_one_system_image('py37', 'cpu'),
            "py37_gpu": self.get_one_system_image('py37', 'gpu'),
            "intel_oneapi_pytorch": self.get_one_system_image('', 'pytorch'),
            "intel_oneapi_tensorflow2": self.get_one_system_image(
                '', 'tensorflow2'
            )
        }

    @staticmethod
    def get_one_system_image(lang, arch):
        try:
            tags = [lang, arch] if lang else [arch]
            image = Client().container_client(
            ).search_jupyter_image(tags)
            return image
        except Exception:
            return ''

    @staticmethod
    def get_project_name(username, default_dict):
        if default_dict[username] == 0:
            default_dict[username] = Project.objects.filter(
                username=username
            ).count()
        default_dict[username] += 1
        return f"devtools{default_dict[username]}"

    @staticmethod
    def prepare_tool_instance_settings(
            parameters, container
    ):
        return {
            "image_path": container,
            "jupyter_cmd": parameters.get("jupyter_cmd", ""),
            "cores_per_node": parameters.get("cores_per_node", 1),
            "gpu_per_node": parameters.get("gpu_per_node", 0),
            "check_timeout": parameters.get(
                "check_timeout", False
            ),
            "run_time": parameters.get("run_time", "24h"),
            "password": ""
        }

    @staticmethod
    def check_user_exist_in_nss(username):
        from pwd import getpwnam
        try:
            getpwnam(username)
        except Exception:
            raise

    @staticmethod
    def check_user_exist_in_db(username):
        try:
            auth_client = Client().auth_client()
            auth_client.get_user_info(username)
        except Exception:
            raise

    def check_user_exists(self, username, not_exists_user):
        if username in not_exists_user:
            raise Exception(f'Could find user: {username}')
        try:
            self.check_user_exist_in_nss(username)
            self.check_user_exist_in_db(username)
        except Exception:
            not_exists_user.add(username)
            raise Exception(
                f'Could find user: {username}'
            )
