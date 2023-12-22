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

from logging import getLogger
from typing import List

import attr
from attr import asdict

logger = getLogger(__name__)


# Some helper functions for gres related functionality
def format_gres(gres_list):
    """ Format gres list to a list of strings which can be added to sacctmgr
    command

    Args:
        gres_list: List of gres dict, each dict should have 'code' and 'value'
            keys

    Returns:
        List of strings which cann be added to sacctmgr command

    Example:
        >>> format_gres([{'code': 'gpu', 'value': '1'}])
        ['gres/gpu=1']
    """
    res = [f"gres/{gres['code']}={gres['value']}"
           for gres in gres_list if gres['value'] != '']
    return res


def index_of_param(param_list, param_name):
    """ Find the index of a parameter in a parameter list where each parameter
    starts with param_name

    Used mainly to find where TRES related parameters are in a parameter list
    """
    for i, param in enumerate(param_list):
        if param.startswith(param_name):
            return i
    raise ValueError(f"Param {param_name} not found")


def add_gres(param_list, gres_name, gres_list):
    """ Add gres to a parameter list

    Args:
        param_list: List of parameters (What will be passed to sacctmgr add qos
            command)
        gres_name: Name of the gres parameter (To differentiate between
            overall, per_user, per_job, etc.)
        gre_list: List of gres dict, each dict should have 'code' and 'value'
            (Where to take gres information from)

    Returns:
        Updated list of parameters with gres added
    """
    gres = format_gres(gres_list)
    if gres:
        index = index_of_param(param_list, gres_name)
        param_list[index] += ',' + ','.join(gres)
    return param_list


@attr.s(slots=True)
class LimitationSetting:
    # Maximum number of running jobs
    max_jobs: int = attr.ib(default=-1)
    # Maximum number of jobs which can be in a pending or running state at any
    # time
    max_submit_jobs: int = attr.ib(default=-1)
    # Maximum wall clock time each job is able to use.
    # Format is <min> or <min>:<sec> or <hr>:<min>:<sec> or
    # <days>-<hr>:<min>:<sec> or <days>-<hr>
    max_runtime: str = attr.ib(default='-1')
    # Maximum number of cpu cores
    max_cpu_cores: int = attr.ib(default=-1)
    # Maximum ammount of memory in MB
    max_memory: int = attr.ib(default=-1)
    # Maximum number of nodes
    max_nodes: int = attr.ib(default=-1)
    # GRES
    gresources: List[dict] = attr.ib(factory=list)


@attr.s(slots=True)
class QueueLimitation:
    name: str = attr.ib()
    overall: LimitationSetting = attr.ib(default=LimitationSetting())
    per_user: LimitationSetting = attr.ib(default=LimitationSetting())
    per_billing_group: LimitationSetting = attr.ib(default=LimitationSetting())
    per_job: LimitationSetting = attr.ib(default=LimitationSetting())
    per_node: LimitationSetting = attr.ib(default=LimitationSetting())

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, lim_info_dict):
        return QueueLimitation(
            name=lim_info_dict["limitation_name"],
            overall=LimitationSetting(
                max_jobs=lim_info_dict.get("overall", {}).get("max_jobs", -1),
                max_submit_jobs=lim_info_dict.get("overall", {}).get(
                    "max_submit_jobs", -1
                ),
                max_cpu_cores=lim_info_dict.get("overall", {}).get(
                    "max_cpu_cores", -1
                ),
                max_memory=lim_info_dict.get("overall", {}).get(
                    "max_memory", -1
                ),
                max_nodes=lim_info_dict.get("overall", {}).get(
                    "max_nodes", -1
                ),
                gresources=lim_info_dict.get("overall", {}).get(
                    "gresources", []
                ),
            ),
            per_user=LimitationSetting(
                max_jobs=lim_info_dict.get("per_user", {}).get("max_jobs", -1),
                max_submit_jobs=lim_info_dict.get("per_user", {}).get(
                    "max_submit_jobs", -1
                ),
                max_cpu_cores=lim_info_dict.get("per_user", {}).get(
                    "max_cpu_cores", -1
                ),
                max_memory=lim_info_dict.get("per_user", {}).get(
                    "max_memory", -1
                ),
                max_nodes=lim_info_dict.get("per_user", {}).get(
                    "max_nodes", -1
                ),
                gresources=lim_info_dict.get("per_user", {}).get(
                    "gresources", []
                ),
            ),
            per_billing_group=LimitationSetting(
                max_jobs=lim_info_dict.get("per_billing_group", {}).get(
                    "max_jobs", -1
                ),
                max_submit_jobs=lim_info_dict.get("per_billing_group", {}).get(
                    "max_submit_jobs", -1
                ),
                max_cpu_cores=lim_info_dict.get("per_billing_group", {}).get(
                    "max_cpu_cores", -1
                ),
                max_memory=lim_info_dict.get("per_billing_group", {}).get(
                    "max_memory", -1
                ),
                max_nodes=lim_info_dict.get("per_billing_group", {}).get(
                    "max_nodes", -1
                ),
                gresources=lim_info_dict.get("per_billing_group", {}).get(
                    "gresources", []
                ),
            ),
            per_job=LimitationSetting(
                max_runtime=(lim_info_dict.get(
                    "per_job", {}).get("max_runtime", "-1") or '-1'
                ),
                max_cpu_cores=lim_info_dict.get("per_job", {}).get(
                    "max_cpu_cores", -1
                ),
                max_memory=lim_info_dict.get("per_job", {}).get(
                    "max_memory", -1
                ),
                max_nodes=lim_info_dict.get("per_job", {}).get(
                    "max_nodes", -1
                ),
                gresources=lim_info_dict.get("per_job", {}).get(
                    "gresources", []
                ),
            ),
            per_node=LimitationSetting(
                max_cpu_cores=lim_info_dict.get("per_node", {}).get(
                    "max_cpu_cores", -1
                ),
                max_memory=lim_info_dict.get("per_node", {}).get(
                    "max_memory", -1
                ),
                gresources=lim_info_dict.get("per_node", {}).get(
                    "gresources", []
                ),
            ),
        )

    def limitation_params_list(self):
        params = [
            f"Name={self.name}",
            # Overall
            f"GrpJobs={self.overall.max_jobs}",
            f"GrpSubmitJobs={self.overall.max_submit_jobs}",
            "GrpTRES="
            f"CPU={self.overall.max_cpu_cores},"
            f"MEM={self.overall.max_memory},"
            f"Node={self.overall.max_nodes}",
            # Per User
            f"MaxJobsPU={self.per_user.max_jobs}",
            f"MaxSubmitJobsPU={self.per_user.max_submit_jobs}",
            "MaxTRESPU="
            f"CPU={self.per_user.max_cpu_cores},"
            f"MEM={self.per_user.max_memory},"
            f"Node={self.per_user.max_nodes}",
            # Per Billing Group
            f"MaxJobsPA={self.per_billing_group.max_jobs}",
            f"MaxSubmitJobsPA={self.per_billing_group.max_submit_jobs}",
            "MaxTRESPA="
            f"CPU={self.per_billing_group.max_cpu_cores},"
            f"MEM={self.per_billing_group.max_memory},"
            f"Node={self.per_billing_group.max_nodes}",
            # Per Job
            f"MaxWall={self.per_job.max_runtime}",
            "MaxTRESPerJob="
            f"CPU={self.per_job.max_cpu_cores},"
            f"MEM={self.per_job.max_memory},"
            f"Node={self.per_job.max_nodes}",
            # Per Node
            "MaxTRESPerNode="
            f"CPU={self.per_node.max_cpu_cores},"
            f"MEM={self.per_node.max_memory}",
        ]

        # Add GRES related information
        gres_mapping = {
            "GrpTRES": self.overall.gresources,
            "MaxTRESPU": self.per_user.gresources,
            "MaxTRESPA": self.per_billing_group.gresources,
            "MaxTRESPerJob": self.per_job.gresources,
            "MaxTRESPerNode": self.per_node.gresources,
        }
        for gres_name, gres_list in gres_mapping.items():
            params = add_gres(params, gres_name, gres_list)

        return params
