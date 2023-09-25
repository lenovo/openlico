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
import os
import re
import shutil
from os import path, remove
from subprocess import check_call, check_output  # nosec B404
from typing import List

from lico.scheduler.base.exception.manager_exception import (
    GresNotAvailableException, NodeNotExistException,
    PerJobMaxRuntimeWrongFormat, QueryLimitationDetailException,
    QueryQueueDetailException, SaveSlurmConfigurationFileException,
)
from lico.scheduler.base.job.queue_state import QueueState
from lico.scheduler.base.setting.queue_limitation import (
    LimitationSetting, QueueLimitation,
)
from lico.scheduler.base.setting.queue_over_subscribe import QueueOverSubscribe
from lico.scheduler.base.setting.queue_setting import QueueNode, QueueSetting

from .job_parser import convert_memory

logger = logging.getLogger(__name__)


def save_slurm_conf():
    pattern_host = re.compile(r'^SlurmctldHost\[\d+\]=(?P<value>.+)$')
    pattern_unknown = re.compile(r'^\w+=[Uu]nknown$')
    pattern_invalid = re.compile(r'^AccountingStorageEnforce=[Nn]one$')

    def _set_root_gid_uid():
        os.setgid(0)
        os.setuid(0)

    try:
        new_config = check_output(  # nosec B603 B607
            ['scontrol', 'write', 'config'],
            preexec_fn=_set_root_gid_uid
        ).decode()
        new_config_path = new_config.split()[-1]
        slurm_conf_path = path.splitext(new_config_path)[0]
        shutil.copyfile(slurm_conf_path, slurm_conf_path + '.bk')

        if is_enabled_hybird_HPC(slurm_conf_path):
            sync_slurm_for_hybird_HPC(new_config_path)

        with open(new_config_path, "r") as f, \
                open(slurm_conf_path, 'w') as f2:
            for line in f:
                match = pattern_host.match(line)
                if pattern_unknown.match(line) is not None:
                    continue
                elif pattern_invalid.match(line) is not None:
                    continue
                elif match is not None:
                    f2.write('SlurmctldHost={value}\n'.format(
                        **match.groupdict())
                    )
                else:
                    f2.write(line)
        remove(new_config_path)
    except Exception as e:
        raise SaveSlurmConfigurationFileException from e


def check_slurm_nodes(nodes: str):
    try:
        check_call(['scontrol', 'show', 'Node', nodes])  # nosec B603 B607
    except Exception as e:
        logger.exception("Scheduler nodes %s not exist.", nodes)
        raise NodeNotExistException from e


def get_queue_detail(q_name=None):
    columns_mapping = {
        'PARTITION': 'queue_name',
        'AVAIL': 'avail',
        'TIMELIMIT': 'timelimit',
        'NODES': 'nodes',
        'STATE': 'state',
        'NODELIST': 'node_list',
        'QOS': 'qos',
    }

    try:
        data = {}
        queue = check_output(['sinfo']).decode()[:-1]  # nosec B603 B607
        title = queue.split('\n')[0].split()
        for q in queue.split('\n')[1:]:
            query = {}
            if q[0] == ' ':
                continue

            q = q.split()
            for i in range(len(title)):
                query[columns_mapping[title[i]]] = \
                    q[title.index(title[i])] if len(q) > i else ""

            queue_name = query['queue_name']
            check_queue = check_output([  # nosec B603 B607
                'sinfo', '-p', queue_name
            ]).decode()
            if len(check_queue.split('\n')[1]) == 0:
                queue_name = queue_name[:-1]   # trim * from default queue_name

            if q_name and q_name != queue_name:
                continue

            node_state = query['state']
            if queue_name not in data:
                queues = check_output(  # nosec B603 B607
                    ['scontrol', 'show', 'partition', '-o', queue_name],
                ).decode()
                queues = dict(
                    map(lambda x: (x.split('=')[0].upper(),
                                   x.split('=')[1]), queues.split()))
                q_node = QueueNode(
                    state=node_state,
                    nodes=int(query['nodes']),
                    nodelist=query['node_list']
                )
                data[queue_name] = QueueSetting(
                    name=queue_name,
                    avail=QueueState[queues['STATE']],
                    priority=int(queues['PRIORITYTIER']),
                    default=(queues['DEFAULT'] == 'YES'),
                    allow_groups=queues['ALLOWGROUPS'].split(','),
                    max_time=queues['MAXTIME'],
                    over_subscribe=QueueOverSubscribe.from_string(
                        queues['OVERSUBSCRIBE']),
                    node_list=[q_node],
                    qos=queues['QOS'],
                )
            else:
                data[queue_name].node_list.append(QueueNode(
                    state=node_state,
                    nodes=int(query['nodes']),
                    nodelist=query['node_list']
                ))
    except Exception as e:
        raise QueryQueueDetailException from e
    return data


def parse_TRES_properties(tres: str):
    """Parse TRES properties

    Args:
        tres: TRES properties
    Returns:
        Dictionary with TRES properties
    """
    str_to_dict = {
        'cpu': 'max_cpu_cores',
        'mem': 'max_memory',
        'node': 'max_nodes',
    }
    tres_dict = {}
    tres_props = tres.split(',')
    if len(tres_props) == 1 and tres_props[0] == '':
        # Only occurs when no TRES properties are set
        return {}

    for t in tres_props:
        tres_name, tres_value = t.split('=')

        if tres_name.startswith('gres'):
            # Dealing with GRES property
            code = tres_name.split('/')[1]
            gres_obj = {"code": code, "value": tres_value}
            try:
                tres_dict["gresources"].append(gres_obj)
            except KeyError:
                # If gresources key does not exist in tres_dict, create it
                tres_dict["gresources"] = [gres_obj]
        else:
            try:
                tres_dict[str_to_dict[tres_name]] = tres_value
            except KeyError:
                # Ignore TRES properties that are not supported by LICO portal
                pass

    if 'max_memory' in tres_dict:
        tres_dict['max_memory'] = convert_memory(
            tres_dict['max_memory']) / 1024
    return tres_dict


def get_limitation_setting(setting, first_index):
    """Get limitation setting

    Args:
        setting: limitation setting
        first_index: index of first setting
    Returns:
        Dictionary with limitation setting, mostly used for unpacking in
        LimitationSetting
    """
    lim_set = {
        "max_jobs": setting[first_index],
        "max_submit_jobs": setting[first_index + 1],
        **parse_TRES_properties(setting[first_index + 2])
    }
    return lim_set


def get_all_limitation_details(lim_name: str = None) -> List[dict]:
    """Get all information about Slurm QoS settings usging 'sacctmgr show qos'

    Args:
        lim_name: specific limitation to query details. If not provided, \
            function returns details for all limitations
    Returns:
        List of dictionaries containing limitation details
    """
    show_format = "format=name,GrpJobs,GrpSubmitJobs,GrpTRES,MaxJobsPU,"\
        "MaxSubmitJobsPU,MaxTRESPerUser,MaxJobsPA,MaxSubmitJobsPA,"\
        "MaxTRESPerAccount,MaxWall,MaxTRES,MaxTRESPerNode"
    try:
        limitations = []
        console_command = ["sacctmgr", "show", "qos", show_format, '-Pn']
        if lim_name is not None:
            console_command.insert(3, lim_name)
        qos_query = check_output(  # nosec B603 B607
            console_command
        ).decode().split("\n")
        for qos in qos_query[:-1]:
            setting = qos.split('|')
            if setting[0] == 'normal':
                continue
            lim = QueueLimitation(
                name=setting[0],
                overall=LimitationSetting(
                    **get_limitation_setting(setting, 1)),
                per_user=LimitationSetting(
                    **get_limitation_setting(setting, 4)),
                per_billing_group=LimitationSetting(
                    **get_limitation_setting(setting, 7)),
                per_job=LimitationSetting(
                    max_runtime=setting[10],
                    **parse_TRES_properties(setting[11])
                ),
                per_node=LimitationSetting(
                    **parse_TRES_properties(setting[12])
                )
            )
            limitations.append(lim.to_dict())
        return limitations
    except Exception as e:
        raise QueryLimitationDetailException from e


def check_runtime_format(runtime):
    runtime_format = re.compile(
        # <days>-<hr>:<min>:<sec>
        r"^((\d+)-)?(\d{1,2}):(\d{1,2}):(\d{1,2})$|"
        # <days>-<hr>
        r"^((\d+)-)?(\d{1,2})$|"
        # <hr>:<min>:<sec>
        r"^(\d{1,2}):(\d{1,2}):(\d{1,2})$|"
        # <hr>:<min>
        r"^(\d{1,2}):(\d{1,2})$|"
        # <min> or -1, but not negative min
        r"^(?:-1|\b\d+\b(?!-))"
    )
    if not runtime_format.match(runtime):
        raise PerJobMaxRuntimeWrongFormat


def check_gres_available(gres_codes):
    """Check if GRES codes from gres.csv are available in Slurm

    Args:
        gres_codes: list of GRES codes
    Returns:
        True if all GRES codes are available, False otherwise
    Raises:
        GresNotAvailableException: if GRES code is not available in Slurm
    """
    tres = check_output([  # nosec B603 B607
        'sacctmgr', 'show', 'tres', '-Pn'
    ]).decode().split('\n')
    slurm_gres = [t.split('|')[1] for t in tres if t.split('|')[0] == 'gres']
    for lico_gres in gres_codes:
        if lico_gres.lower() not in slurm_gres:
            raise GresNotAvailableException(lico_gres)


HYBIRD_SLURM_CONF = "/opt/lico/cloud/azure/slurm.conf"


def is_enabled_hybird_HPC(slurm_conf):

    with open(slurm_conf, 'r') as f:
        content = f.read()
    pattern = re.compile(r'[^#]include\s+/opt/lico/cloud/azure/slurm.conf')
    result = pattern.search(content)
    if result:
        return True
    return False


def sync_slurm_for_hybird_HPC(slurm_conf):
    with open(slurm_conf, 'r') as f:
        content = f.read()

    with open(HYBIRD_SLURM_CONF, "r") as hybird_file:
        for line in hybird_file:
            if not line.startswith('#') and line.strip():
                kw = line.strip().split()[0]
                content = re.sub(r'{}.*'.format(kw), '', content)
    content = content + '\n' + 'include /opt/lico/cloud/azure/slurm.conf\n'
    with open(slurm_conf, 'w') as f:
        content = re.sub(r'MaxNodeCount=.*', '', content)
        f.write(content)

