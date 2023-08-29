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

import os

from django import template

from ..exceptions import UnknownSchedulerException

register = template.Library()


@register.simple_tag
def program_exec(program, pre_program=""):
    ext = os.path.splitext(program)[-1]
    commands_dir = {
        '.py': 'python ',
        '.pyc': 'python ',
        '.sh': 'bash '
    }
    return commands_dir.get(ext) + pre_program + program


@register.simple_tag
def scheduler_exec(scheduler, gpu_per_worker, gpu_per_node, dis):
    # after scheduler exec command must be nodename
    if scheduler == "slurm":
        sched_exec_cmd = "srun -N1 -n1"
        if dis:
            sched_exec_cmd += " --cpu_bind=cores"
        # if gpu_per_node:
        #     sched_exec_cmd += " --gres=gpu:" + str(gpu_per_worker)
        return sched_exec_cmd + " -l --nodelist="
    elif scheduler == "pbs":
        return "pbs_tmrsh "
    elif scheduler == "lsf":
        return "lsrun -m "
    else:
        raise UnknownSchedulerException


@register.simple_tag
def get_exec_node(scheduler, is_multinode, cores_per_node=1):
    if scheduler == "slurm":
        if is_multinode:
            cmd = "exec_nodes=(`scontrol show hostname " \
                  "${SLURM_JOB_NODELIST}`)"
        else:
            cmd = 'exec_node=${SLURM_JOB_NODELIST}\n' \
                  'cpu_curr_node=${SLURM_CPUS_ON_NODE}\n' \
                  'if [ "${cpu_curr_node}" = "" ]; then ' \
                  ' cpu_curr_node=%s; fi' % cores_per_node
    elif scheduler == "lsf":
        if is_multinode:
            cmd = "exec_nodes=(`echo ${LSB_MCPU_HOSTS} | tr ' ' '\n' | " \
                  "awk '{if(NR%2!=0)print $1}' | tr '\n' ' '`)"
        else:
            cmd = "exec_node=`echo ${LSB_MCPU_HOSTS} | awk '{print $1}'`"
    elif scheduler == "pbs":
        if is_multinode:
            cmd = "exec_nodes=(`cat ${PBS_NODEFILE} | tr '\n' ' '`)"
        else:
            cmd = "exec_node=`cat ${PBS_NODEFILE}`"
    else:
        raise UnknownSchedulerException
    return cmd
