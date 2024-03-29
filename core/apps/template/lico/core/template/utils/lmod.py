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

from django.conf import settings

from ..exceptions import ModuleInvalid
from ..models import Module, ModuleItem
from ..utils.common import exec_oscmd_with_user, exec_ssh_oscmd_with_user

logger = logging.getLogger(__name__)


def sync(content):
    if isinstance(content, dict):
        _clear_module()
        for name, modules in content.items():
            _process_module(name, modules)


def _clear_module():
    Module.objects.all().delete()


def _process_module(name, modules):
    module = Module.objects.create(name=name)
    for item_name, item in modules.items():
        if 'hidden' in item:
            if not item['hidden']:
                _process_module_item(module, item_name, item)
        elif 'markedDefault' in item:
            if not item['markedDefault']:
                _process_module_item_for_ubuntu(module, item_name, item)


def _process_module_item(module, item_name, item):
    item_version = item.get('Version')
    version = item_version.strip() if item_version else None

    parents = item.get('parentAA')
    if parents is not None:
        parents = ','.join(parents[0])

    location = _process_module_location(module, item)

    ModuleItem.objects.create(
        module=module,
        path=item_name,
        version=version,
        name=item['fullName'],
        category=item.get('Category'),
        description=item.get('Description'),
        parents=parents,
        location=location
    )


def _process_module_location(module, item):
    """
        item example:
        "/opt/ohpc/pub/modulefiles/EasyBuild/4.6.2": {
            "lpathA": {
                "/opt/ohpc/easybuild/4.6.2/software/EasyBuild/4.6.2/lib": 1
            },
            "whatis": [
                "Name: easybuild",
                "Version: 4.6.2",
                "Category: system tool",
                "Description: Software build and installation framework",
                "URL: https://easybuilders.github.io/easybuild/"
            ],
            "help": " \nThis module loads easybuild\n\nVersion 4.6.2\n\n",
            "Description": "Software build and installation framework",
            "hidden": false,
            "mpath": "/opt/ohpc/pub/modulefiles",
            "fullName": "EasyBuild/4.6.2",
            "URL": "https://easybuilders.github.io/easybuild/",
            "Version": "4.6.2",
            "pathA": {
                "/opt/ohpc/admin/lmod/lmod/libexec": 1,
                "/opt/ohpc/easybuild/4.6.2/software/EasyBuild/4.6.2/bin": 1
            },
            "Category": "system tool"
        }

        - lpathA: library path
        - mpath: module file path
        - pathA: binary path
    """
    binary_path = item.get("pathA", dict())
    location_list = list(binary_path.keys())

    library_path = item.get("lpathA", dict())
    location_list += list(library_path.keys())

    location = "\n".join(location_list)
    return location


def _process_module_item_for_ubuntu(module, item_name, item):
    item_version = item.get('full')
    version = item_version.strip() if item_version else None
    version = version.split("/")[1]

    parents = item.get('parentAA')
    if parents is not None:
        parents = ','.join(parents[0])

    location = _process_module_location(module, item)

    ModuleItem.objects.create(
        module=module,
        path=item_name,
        version=version,
        name=item['full'],
        category=item.get('Category'),
        description=item.get('Description'),
        parents=parents,
        location=location
    )


def lmod_verify(user, host, port, modules, role="admin"):
    module_path = settings.TEMPLATE.MODULE_PATH
    module_verify = ["module", "--force", "purge", ";", "module", "load"]
    module_verify.extend(modules)
    if role != "admin":
        if hasattr(settings, "USERMODULE"):
            eb_utils = settings.USERMODULE.EASYBUILDUTILS[
                'EasyBuildUtils'](user)
            private_modulepath = eb_utils.get_eb_module_file_path()
            module_path = module_path + ":" + private_modulepath
    module_cmd = ["export", "MODULEPATH="+module_path, ";"]
    module_cmd.extend(module_verify)

    if host:
        rc, out, err = exec_ssh_oscmd_with_user(
            host, port, user.username, module_cmd
        )
    else:
        rc, out, err = exec_oscmd_with_user(user.username, module_cmd)
    if rc != 0:
        logger.exception("Verify modules fail: %s", modules)
        raise Exception(err)


def verify_modules(user, modules, role="admin"):
    host = settings.JOB.JOB_SUBMIT_NODE_HOSTNAME
    host_port = settings.JOB.JOB_SUBMIT_NODE_PORT
    try:
        lmod_verify(user, host, host_port, modules, role)
    except Exception as e:
        logger.exception("Verify modules fail: %s", modules)
        raise ModuleInvalid(output=str(e)) from e
