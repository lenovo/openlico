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

import copy

from django.conf import settings

from lico.core.template.models.runtime import (
    RuntimeEnv, RuntimeModule, RuntimeScript,
)


def runtime_distinct(runtime_id):
    origin_module_list = []
    origin_env_list = []
    env_list = []
    script_list = []
    for id in runtime_id:
        modules = RuntimeModule.objects.filter(
            runtime_id=id
        ).values("module", "parents")
        envs = RuntimeEnv.objects.filter(
            runtime_id=id
        ).values("name", "value")
        scripts = RuntimeScript.objects.filter(
            runtime_id=id
        ).values("filename")

        for module in modules:
            parents = module['parents']
            module['parents'] = [] \
                if parents is None or len(parents) == 0 \
                else parents.split(',')
            origin_module_list.append(module)

        for env in envs:
            if list(env.values())[0] not in origin_env_list:
                origin_env_list.append(list(env.values())[0])
                env_list.append(env)

        for script in scripts:
            if script not in script_list:
                script_list.append(script)
    module_list = module_distinct(origin_module_list)
    return module_list, env_list, script_list


def module_distinct(origin_module_list):
    new_module_list = copy.deepcopy(origin_module_list)
    replace_module_list = []
    for module_dict in origin_module_list:
        if '/' not in module_dict['module']:
            replace_module_list.append(module_dict)
        elif '/' in module_dict['module']:
            module_name = module_dict['module'].split('/')[0]
            module_dict['module'] = module_name
            replace_module_list.append(module_dict)

    distinct_origin_list = []
    module_list = []
    for index, module_dict in enumerate(replace_module_list):
        if module_dict not in distinct_origin_list:
            distinct_origin_list.append(module_dict)
            module_list.append(new_module_list[index])

    return module_list


def script_filter(scripts, tag):
    path = settings.ONEAPI.INTEL_MODULE_PATH
    path = path if path.endswith('/') else path + '/'
    have_script = __have_intel_script(scripts, path)
    if not tag and have_script:
        tag = "sys:intel"
    return tag


def __have_intel_script(scripts, path):
    have_script = False
    if scripts:
        script = list(filter(
            lambda x: x.startswith(path), scripts))
        if len(script) > 0:
            have_script = True
    return have_script
