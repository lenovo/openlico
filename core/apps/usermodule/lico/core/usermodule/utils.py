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
import ast
import json
import logging
import os
from subprocess import PIPE, run  # nosec B404

import yaml
from attr import asdict, attrib, attrs
from django.conf import settings

from lico.core.contrib.client import Client

from .exceptions import (
    ModulepathNotExistedException, SpiderToolNotAvailableException,
    UserModuleGetPrivateModuleException,
)

logger = logging.getLogger(__name__)

MODULE_FILE_DIR = "modules/all"
SOFTWARE_DIR = "software"


@attrs
class Module:
    name = attrib(type=str)
    path = attrib(type=str)
    version = attrib(type=str)
    category = attrib(type=str)
    description = attrib(type=str)
    parents = attrib(type=str)
    location = attrib(type=str)


def exec_oscmd(args, timeout=30):
    process = run(  # nosec B603
        args, stdout=PIPE, stderr=PIPE, timeout=timeout
    )
    return process.returncode, process.stdout, process.stderr


def get_eb_prefix(workspace):
    return os.path.join(workspace, settings.USERMODULE.WORK_PATH)


def get_eb_module_file_path(workspace, module_name=None):
    file_path = os.path.join(get_eb_prefix(workspace), MODULE_FILE_DIR)
    if module_name is not None:
        file_path = os.path.join(file_path, f"{module_name}.lua")
    return file_path


def get_eb_software_path(workspace, module_name=None):
    software_path = os.path.join(get_eb_prefix(workspace), SOFTWARE_DIR)
    if module_name is not None:
        software_path = os.path.join(software_path, module_name)
    return software_path


def get_private_module(spider, workspace):
    module_path = get_eb_module_file_path(workspace)

    if not os.path.exists(module_path):
        raise ModulepathNotExistedException

    if not os.path.exists(spider):
        raise SpiderToolNotAvailableException

    rc, output, err = exec_oscmd([spider, '-o', 'spider-json', module_path])
    if err:
        logger.error(
            "Failed to get modules output. "
            "Error message is: %s", err.decode()
        )
        raise UserModuleGetPrivateModuleException(err.decode())

    private_module_content = json.loads(output)
    private_module = process_module(private_module_content, workspace)

    return private_module


def process_module(content, workspace):
    software_path = get_eb_software_path(workspace)
    module_list = list()
    for name, modules in content.items():
        module_dict = {
            "name": name,
            "items": list(),
            "type": "private"
        }
        for item_name, item in modules.items():
            version = item.get("Version") if item.get("Version") else None
            location = os.path.join(software_path, name, version)
            module = Module(
                name=item.get("fullName"),
                path=item_name,
                version=version,
                category=item.get("Category"),
                description=item.get("Description"),
                parents=item.get('parentAA'),
                location=location
            )
            item_dict = asdict(module)
            item_dict["type"] = "private"

            module_dict["items"].append(item_dict)
        module_list.append(module_dict)
    return module_list


def get_fs_operator(user):
    return Client().filesystem_client(user=user)


def convert_myfolder(fopr, user, origin_path):
    if not origin_path.startswith('MyFolder'):
        return origin_path
    return fopr.path_abspath(
        fopr.path_join(
            user.workspace,
            fopr.path_relpath(
                origin_path,
                start='MyFolder'
            )
        )
    )


class EasyConfigParser(object):
    HEADER_MANDATORY = ['version', 'name', 'homepage',
                        'description']
    YEB_FORMAT_EXTENSION = '.yeb'

    def __init__(self, filename=None, content=''):
        self.filename = filename
        self.content = content

    def _is_yeb_format(self):
        is_yeb = False
        if self.filename:
            is_yeb = os.path.splitext(self.filename)[-1] == \
                     self.YEB_FORMAT_EXTENSION
        else:
            for line in self.content.splitlines():
                if line.startswith('name: '):
                    is_yeb = True
        return is_yeb

    def parse(self):
        if self._is_yeb_format():
            return self._parse_yeb_header()
        else:
            return self._parse_eb_header()

    def _parse_eb_header(self):
        eb_ast_node = ast.parse(self.content)
        header_dict = {e: "" for e in self.HEADER_MANDATORY}
        for node in ast.walk(eb_ast_node):
            try:
                if isinstance(node, ast.Assign):
                    node_target_id = node.targets[0].id
                    if node_target_id in self.HEADER_MANDATORY:
                        if isinstance(node.value, ast.Str):
                            header_dict[node_target_id] = node.value.s
                        elif isinstance(node.value, ast.Constant):
                            header_dict[node_target_id] = node.value.value
            except Exception as e:
                logger.info(e)
                continue

        return header_dict

    def _parse_yeb_header(self):
        yeb_content = yaml.safe_load(self.content)
        header_dict = {e: "" for e in self.HEADER_MANDATORY}
        for hm in self.HEADER_MANDATORY:
            header_dict[hm] = yeb_content.get(hm)

        return header_dict


class UserModuleJobHelper(object):
    def __init__(self, username=None):
        if username is None:
            self._job_client = Client().job_client()
            self._template_client = Client().template_client()
        else:
            self._job_client = Client().job_client(username=username)
            self._template_client = Client().template_client(username=username)

    def submit_module_job(self, template_id, template_param_vals):
        template_job = self._template_client.submit_template_job(
            template_id, template_param_vals
        )
        return template_job
