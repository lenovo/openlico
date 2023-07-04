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

import re
from subprocess import run  # nosec B404

from django import template
from django.db.models import Q
from six import raise_from

from lico.core.template.exceptions import RuntimeNotExist
from lico.core.template.models.runtime import Runtime
from lico.core.template.utils.runtime import runtime_distinct
from lico.password import fetch_pass

register = template.Library()


@register.simple_tag
def add_vtune_group(user):
    """
    Bug 261903 : After the node is restarted, the vtune driver
    installed on the node will disappear.
    """
    _, password = fetch_pass('ldap')
    command = ["su", "-c",
               f"echo {password} | lgroupadd vtune;"
               f"echo {password} | lgroupmod -M {user} vtune"]
    state = run(command)  # nosec B603
    if state.returncode:
        return "echo 'Add vtune group failed.'"
    else:
        return "echo 'Add vtune group success.'"


@register.simple_tag
def runtime_sh(user, runtime_id, affinity_id=None):
    result = ''
    if runtime_id:
        try:
            runtime_queryset = Runtime.objects.filter(
                Q(username=user.username) | Q(username='')
            )

            module_list, env_list, script_list = runtime_query_filter(
                runtime_id, runtime_queryset
            )

            if affinity_id and type(affinity_id) == int:
                affinity_filter = Runtime.objects.filter(
                    username=user.username).get(id=affinity_id)
                module_list = module_list + affinity_filter.module_list
                env_list = env_list + affinity_filter.env_list
                script_list = script_list + affinity_filter.script_list

            module_str = 'module purge \n' if module_list else ''
            for module in module_list:
                module_str += "module try-load {} \n".format(module)
            env_str = ''
            for env in env_list:
                env_str += "export {} \n".format(env)
            script_str = ''
            for script in script_list:
                script_str += "source {!r} \n".format(script)
            result = script_str + module_str + env_str
        except Runtime.DoesNotExist as e:
            raise_from(RuntimeNotExist, e)
    return result


@register.simple_tag
def chainer_cpus_per_task(gpu_per_node, cores_per_node):
    return int((cores_per_node + gpu_per_node - 1) / gpu_per_node)


@register.filter
def is_use_gpu(gpu_resource_name):
    return gpu_resource_name.lower() not in ["null", "none"]


@register.filter
def timeformat(time):
    timestrip = time.strip()
    daystr = re.match(r'.*?(\d+)d.*?', timestrip)
    hourstr = re.match(r'.*?(\d+)h.*?', timestrip)
    minutestr = re.match(r'.*?(\d+)m.*?', timestrip)
    day = '0' if daystr is None else daystr.group(1)
    hour = '00' if hourstr is None else hourstr.group(1)
    minute = '00' if minutestr is None else minutestr.group(1)
    formattime = day + '-' + hour + ':' + minute
    return formattime


def runtime_query_filter(runtime_id, runtime_queryset):
    if isinstance(runtime_id, int):
        runtime_filter = runtime_queryset.get(id=runtime_id)
        module_list = runtime_filter.module_list
        env_list = runtime_filter.env_list
        script_list = runtime_filter.script_list
    elif isinstance(runtime_id, list):
        runtime_filter = runtime_queryset.filter(id__in=runtime_id)
        if len(runtime_id) == len(runtime_filter):
            module_list, env_list, script_list = runtime_distinct(
                runtime_id
            )
            module_list = [module['module'] for module in module_list]
            env_list = [f"{env['name']}={env['value']}"
                        for env in env_list]
            script_list = [script['filename']
                           for script in script_list]
        else:
            raise RuntimeNotExist
    return module_list, env_list, script_list
