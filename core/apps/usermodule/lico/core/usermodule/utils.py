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
from subprocess import PIPE, list2cmdline, run  # nosec B404

import yaml
from attr import asdict, attrib, attrs
from django.conf import settings

from lico.core.contrib.client import Client

from .exceptions import (
    SpiderToolNotAvailableException, UserModuleConfigsException,
    UserModuleFailToGetJobException, UserModuleGetPrivateModuleException,
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


def exec_oscmd_with_user(user, args, timeout=30):
    process = run(  # nosec B603 B607
        [
            'su', '-', user, '-c',
            list2cmdline(args)
        ],
        stdout=PIPE,
        stderr=PIPE,
        timeout=timeout
    )
    return process.returncode, process.stdout, process.stderr


class EasyBuildUtils():
    def __init__(self, user):
        self.user = user

    def get_eb_prefix(self):
        return os.path.join(self.user.workspace, settings.USERMODULE.WORK_PATH)

    def get_eb_module_file_path(self, module_name=None):
        file_path = os.path.join(self.get_eb_prefix(), MODULE_FILE_DIR)
        if module_name is not None:
            file_path = os.path.join(file_path, f"{module_name}.lua")
        return file_path

    def get_eb_software_path(self, module_name=None):
        software_path = os.path.join(self.get_eb_prefix(), SOFTWARE_DIR)
        if module_name is not None:
            software_path = os.path.join(software_path, module_name)
        return software_path

    def get_eb_configs(self, param='', is_alnum=True):
        """
        For alphabet: eb --search=^A.*eb$
        For number: eb --search=^[0-9].*eb$
        For searching by name: eb --search=<param>.*eb$
        """
        pattern = param

        if is_alnum:
            if param == '0':
                pattern = "^[0-9].*eb$"
            else:
                pattern = f"^{param}.*eb$"

        args = ["module", "try-load", "EasyBuild",
                ";", "eb", f"--search={pattern}"]
        code, out, err = exec_oscmd_with_user(self.user.username, args)

        if err:
            logger.exception("Failed to get usermodule configs.")
            raise UserModuleConfigsException(err.decode())

        def parse_configs(config):
            if config.startswith(" * "):
                return config.split(" * ")[-1]

        return map(parse_configs, out.decode().splitlines())


def get_private_module(spider, user):
    eb_utils = EasyBuildUtils(user)
    module_path = eb_utils.get_eb_module_file_path()

    if not os.path.exists(module_path):
        return list()

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
    private_module = process_module(private_module_content, user)

    return private_module


def process_module(content, user):
    eb_utils = EasyBuildUtils(user)
    software_path = eb_utils.get_eb_software_path()
    module_list = list()
    if not content:
        return module_list

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
                parents=item.get('parentAA', list()),
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
    BUILD_JOB_LABEL = ['version', 'name', 'homepage', 'description']
    PARSE_FILENAME = ['name', 'version', 'toolchain', 'versionsuffix']
    YEB_FORMAT_EXTENSION = '.yeb'

    EXIST = 1
    NOTEXIST = 0

    def __init__(self, filename=None, content='', parse_with_name=False):
        self.filename = filename
        self.content = content
        self.book = {}
        self.parse_with_name = parse_with_name

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

    def get_ast_str(self, node):
        return node.s

    def get_ast_constant(self, node):
        return node.value

    def get_ast_num(self, node):
        return node.n

    def get_ast_name_toolchain_only(self, node, target_id):
        value = ""
        if target_id == "toolchain":
            value = node.id
        return value

    def get_ast_values(self, node, header_dict):
        targets = node.targets
        for target in targets:
            if not hasattr(target, 'id'):
                continue
            if target.id in self.book.keys():
                self.book[target.id] = self.EXIST
                if isinstance(node.value, ast.Name):
                    header_dict[target.id] = \
                        self.get_ast_name_toolchain_only(node.value, target.id)
                elif isinstance(node.value, ast.Str):
                    header_dict[target.id] = self.get_ast_str(node.value)
                elif isinstance(node.value, ast.Num):
                    header_dict[target.id] = self.get_ast_num(node.value)
                elif isinstance(node.value, ast.Constant):
                    header_dict[target.id] = self.get_ast_constant(node.value)
        return

    def get_parameters(self, suffix, header_dict):
        # Filename looks like: <name>-<version>.eb
        # Output: header_dict["version"] = "<version>"
        #         header_dict["toolchain"] = "SYSTEM"
        if header_dict["toolchain"].lower() == "system" \
                and self.book["versionsuffix"] == self.NOTEXIST:
            header_dict["toolchain"] = "SYSTEM"
            header_dict["version"] = suffix.split('-', 1)[1]

        # Filename looks like: <name>-<version>-<versionsuffix>.eb
        # Output: header_dict["version"] = "<version>-<versionsuffix>"
        #         header_dict["toolchain"] = "SYSTEM"
        elif header_dict["toolchain"].lower() == "system" \
                and self.book["versionsuffix"] == self.EXIST:
            header_dict["toolchain"] = "SYSTEM"
            _, header_dict["version"] = suffix.split('-', 1)

        # Filename looks like: <name>-<version>-<toolchain>-<versionsuffix>.eb
        # or: <name>-<version>-<toolchain>.eb
        # Output: header_dict["version"] = "<version>"
        #         header_dict["toolchain"] = "<toolchain>-<versionsuffix>"
        #      or header_dict["toolchain"] = "<toolchain>"
        elif header_dict["toolchain"].lower() != "system":
            version = ""
            toolchain = ""
            if header_dict["version"]:
                version = header_dict["version"]
                toolchain = suffix.split(version, 1)[-1]
                if toolchain.startswith('-'):
                    toolchain = toolchain[1:]
            else:
                if '-' in suffix[1:]:
                    version, toolchain = suffix[1:].split('-', 1)

            header_dict["toolchain"] = toolchain
            header_dict["version"] = version

        return

    def _parse_eb_header(self):
        filename = os.path.basename(self.filename)
        pkg_name = os.path.dirname(self.filename).split("/")[-1]
        suffix = filename.split(pkg_name, 1)[-1].rsplit(".eb", 1)[0]

        if self.parse_with_name:
            header_dict = {e: "" for e in self.PARSE_FILENAME}
            self.book = {e: self.NOTEXIST for e in self.PARSE_FILENAME}
            self._parse_easyconfig_with_filename(suffix, header_dict)
        else:
            header_dict = {e: "" for e in self.BUILD_JOB_LABEL}
            self.book = {e: self.NOTEXIST for e in self.BUILD_JOB_LABEL}
            self._parse_provided_easyconfig_file(header_dict)

        header_dict["filename"] = filename

        return header_dict

    def _parse_easyconfig_with_filename(self, suffix, header_dict):
        eb_ast_node = ast.parse(self.content)
        for node in ast.iter_child_nodes(eb_ast_node):
            if (sum(self.book.values()) == len(self.book)):
                break
            if isinstance(node, ast.Assign):
                self.get_ast_values(node, header_dict)

        self.get_parameters(suffix, header_dict)

        return header_dict

    def _parse_provided_easyconfig_file(self, header_dict):
        eb_ast_node = ast.parse(self.content)
        for node in ast.iter_child_nodes(eb_ast_node):
            if (sum(self.book.values()) == len(self.book)):
                break
            if isinstance(node, ast.Assign):
                self.get_ast_values(node, header_dict)

        return header_dict

    def _parse_yeb_header(self):
        yeb_content = yaml.safe_load(self.content)
        header_dict = {e: "" for e in self.BUILD_JOB_LABEL}
        for hm in self.BUILD_JOB_LABEL:
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

    def query_job(self, job_id):
        try:
            job = self._job_client.query_job(job_id)
            return job
        except Exception:
            raise UserModuleFailToGetJobException(
                "Failed to get job. Job id = {}".format(job_id)
            )

    def cancel_job(self, job_id):
        self._job_client.cancel_job(job_id)
