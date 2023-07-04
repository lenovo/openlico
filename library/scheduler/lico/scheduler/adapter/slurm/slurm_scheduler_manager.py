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
import re
from collections import defaultdict
from subprocess import check_call, check_output  # nosec B404
from typing import List

from lico.scheduler.base.exception.manager_exception import (
    AccountNotExistException, CreateAccountException,
    CreateAssociationException, CreateLimitationException,
    CreateQueueException, DeleteAssociationException,
    DeleteLimitationException, DeleteQueueException,
    LimitationAlreadyExistException, LimitationInUseException,
    LimitationNotExistException, PerJobMaxRuntimeWrongFormat,
    QueryAccountException, QueryLimitationException, QueryNodeStateException,
    QueryQueueException, QuerySlurmctlServiceStatusException,
    QueueAlreadyExistException, QueueBusyException, QueueNotExistException,
    SaveSlurmConfigurationFileException, UnknownActionException,
    UpdateLimitationException, UpdateNodeStateException, UpdateQueueException,
    UpdateQueueStateException,
)
from lico.scheduler.base.scheduler_manager import ISchedulerManager
from lico.scheduler.base.setting.association import Association
from lico.scheduler.base.setting.queue_limitation import QueueLimitation
from lico.scheduler.base.setting.queue_setting import QueueSetting
from lico.scheduler.utils.cmd_utils import exec_oscmd

from .utils.manager_utils import (
    check_runtime_format, check_slurm_nodes, get_all_limitation_details,
    get_queue_detail, save_slurm_conf,
)

logger = logging.getLogger(__name__)


class SchedulerManager(ISchedulerManager):
    def __init__(
            self,
            operator_username: str,
            timeout: int = 30,
    ):
        self._operator_username = operator_username
        self._timeout = timeout

    def is_scheduler_node(self):
        """
        if lico and slurmctld are installed in the same node.
        :return: True or Flase
        """
        try:
            rc, out, err = exec_oscmd(
                ["service", "slurmctld", "status"],
                timeout=self._timeout
            )
            lines = out.decode().splitlines()
            for line in lines:
                if re.search(r'Active: active \(running\)', line):
                    return True
        except Exception as e:
            raise QuerySlurmctlServiceStatusException from e
        return False

    ####################################################################
    # Scheduler Queue
    ####################################################################
    def query_all_queue_settings(self) -> List[QueueSetting]:
        return list(get_queue_detail().values())

    def query_queue_setting(self, queue_name) -> QueueSetting:
        q_detail_dict = get_queue_detail(queue_name)
        if not q_detail_dict.get(queue_name):
            logger.error("Queues name '%s' not exist.", queue_name)
            raise QueueNotExistException
        return q_detail_dict[queue_name]

    def create_queue_setting(self, queue_setting: QueueSetting) -> dict:
        qs = queue_setting
        try:
            queue = check_output(  # nosec B603 B607
                ['sinfo', '-p', qs.name]
            ).decode()
        except Exception as e:
            logger.exception("Query queue '%s' failed.", qs.name)
            raise QueryQueueException from e
        if len(queue.split('\n')[1]) > 0:
            logger.error("Queues '%s' already exist.", qs.name)
            raise QueueAlreadyExistException

        check_slurm_nodes(qs.nodes)
        try:
            check_call([ # nosec B603 B607
                'scontrol', 'create', *qs.queue_params_list()
            ])
            save_slurm_conf()
            is_scheduler_node = self.is_scheduler_node()
        except (
                SaveSlurmConfigurationFileException,
                QuerySlurmctlServiceStatusException
        ):
            raise
        except Exception as e:
            logger.exception("Create queue '%s' failed.", qs.name)
            raise CreateQueueException from e
        return {"is_scheduler_node": is_scheduler_node}

    def update_queue_setting(self, queue_setting: QueueSetting) -> dict:
        new_qs = queue_setting
        check_slurm_nodes(new_qs.nodes)
        try:
            check_call([ # nosec B603 B607
                'scontrol', 'update', *new_qs.queue_params_list()
            ])
            save_slurm_conf()
            is_scheduler_node = self.is_scheduler_node()
        except (
                SaveSlurmConfigurationFileException,
                QuerySlurmctlServiceStatusException
        ):
            raise
        except Exception as e:
            logger.exception("Update queue '%s' failed.", new_qs.name)
            raise UpdateQueueException from e
        return {"is_scheduler_node": is_scheduler_node}

    def delete_queue_setting(self, queue_name) -> dict:
        try:
            queue = check_output( # nosec B603 B607
                ['sinfo', '-p', queue_name]
            ).decode()
            is_used = check_output( # nosec B603 B607
                ['squeue', '-p', queue_name]
            ).decode()
        except Exception as e:
            logger.exception("Query queue '%s' failed.", queue_name)
            raise QueryQueueException from e
        if len(queue.split('\n')[1]) <= 0:
            logger.error("Queues name '%s' not exist.", queue_name)
            raise QueueNotExistException
        if len(is_used.split('\n')[1]) > 0:
            logger.error("Queue '%s' is busy now.", queue_name)
            raise QueueBusyException
        try:
            check_call( # nosec B603 B607
                ['scontrol', 'delete', f'PartitionName={queue_name}']
            )
            save_slurm_conf()
            is_scheduler_node = self.is_scheduler_node()
        except (
                SaveSlurmConfigurationFileException,
                QuerySlurmctlServiceStatusException
        ):
            raise
        except Exception as e:
            logger.exception("Delete queue '%s' failed.", queue_name)
            raise DeleteQueueException from e
        return {"is_scheduler_node": is_scheduler_node}

    def update_queue_state(self, queue_name, queue_state) -> dict:
        try:
            parameters = 'PartitionName={} State={}'.format(
                queue_name, queue_state).split()
            check_call([ # nosec B603 B607
                'scontrol', 'update', *parameters
            ])
            save_slurm_conf()
            is_scheduler_node = self.is_scheduler_node()
        except (
                SaveSlurmConfigurationFileException,
                QuerySlurmctlServiceStatusException
        ):
            raise
        except Exception as e:
            logger.exception(
                "Update queue '%s' queue state failed.", queue_name
            )
            raise UpdateQueueStateException from e
        return {"is_scheduler_node": is_scheduler_node}

    ####################################################################
    # Scheduler Node
    ####################################################################
    def query_node_state(self, node_str: str) -> dict:
        data = {'node_states': defaultdict(list), 'details': ''}
        if not node_str:
            return data
        node_set = set(node_str.replace(',', ' ').strip().split())
        rc, out, err = exec_oscmd(
            ["scontrol", "show", 'Node', ','.join(node_set)], timeout=30
        )
        if not out:
            logger.exception('Get nodes detail failed!'
                             'Error message is : {0}'.format(err.decode()))
            raise QueryNodeStateException(err.decode())
        details = out.decode()
        node_names = re.findall(r'NodeName=([^\s]+)', details, re.I)
        states = re.findall(r'State=([^\s]+)', details, re.I)
        data['details'] = details
        data['return_code'] = rc
        if node_names and states:
            data['node_states']['nodes'] = node_names
            data['node_states']['states'] = states
        if rc:
            nodes = list(node_set - set(node_names))
            pattern = r'(.*\ ({0})+\ .*)\n'.format('|'.join(nodes))
            # states_list:
            # [('Node c9 not found', 'c9'), ('Node c8 not found', 'c8')]
            states_list = re.findall(pattern, details)
            if not states_list:
                return data
            err_nodes = list(map(lambda detail: detail[1], states_list))
            err_states = list(map(lambda detail: detail[0], states_list))
            data['node_states']['nodes'].extend(err_nodes)
            data['node_states']['states'].extend(err_states)
        return data

    def update_node_state(self, node_list, action: str):
        # action: ["resume", "down"]
        columns_mapping = {
            'resume': 'resume',
            'down': 'down'
        }
        if action in columns_mapping:
            action = columns_mapping[action]
        else:
            logger.error("Unknown action for updating node state: %s.", action)
            raise UnknownActionException

        try:
            nodename = "Nodename={}".format(node_list.replace(' ', ','))
            state = "State={}".format(action)
            list_cmd = ["scontrol", "update", nodename, state]
            if action == 'down':
                list_cmd.append("Reason=down by {}".format(
                    self._operator_username)
                )
            check_call(list_cmd) # nosec B603
        except Exception as e:
            raise UpdateNodeStateException from e

    ####################################################################
    # Scheduler QoS
    ####################################################################
    def query_all_limitations(self) -> List[dict]:
        return get_all_limitation_details()

    def query_limitation_setting(self, limitation_name) -> QueueLimitation:
        limitation = get_all_limitation_details(limitation_name)
        if len(limitation) == 0:
            logger.error("Limitation name '%s' not exist.", limitation_name)
            raise LimitationNotExistException
        return limitation[0]

    def create_limitation(self, new_lim: QueueLimitation) -> dict:
        try:
            limitation = check_output([  # nosec B603 B607
                'sacctmgr', 'show', 'qos', new_lim.name,
                'format=name', '-Pn'
            ]).decode()
        except Exception as e:
            logger.exception("Query limitation '%s' failed.", new_lim.name)
            raise QueryLimitationException from e
        if len(limitation.split('\n')) > 1:
            logger.error("Limitation '%s' already exists.", new_lim.name)
            raise LimitationAlreadyExistException

        try:
            check_runtime_format(new_lim.per_job.max_runtime)
        except PerJobMaxRuntimeWrongFormat:
            raise

        try:
            # flake8: noqa: E501
            check_call([ # nosec B603 B607
                "sacctmgr", "-i", "add", "qos", *new_lim.limitation_params_list()
            ])
            save_slurm_conf()
            is_scheduler_node = self.is_scheduler_node()
        except (
                SaveSlurmConfigurationFileException,
                QuerySlurmctlServiceStatusException
        ):
            raise
        except Exception as e:
            logger.exception("Create limitation '%s' failed.", new_lim.name)
            raise CreateLimitationException from e
        return {"is_scheduler_node": is_scheduler_node}

    def update_limitation_setting(self, lim_setting: QueueLimitation) -> dict:
        try:
            check_call([  # nosec B603 B607
                'sacctmgr', '-i', 'modify', 'qos',
                lim_setting.name, 'set', *lim_setting.limitation_params_list()
            ])
            save_slurm_conf()
            is_scheduler_node = self.is_scheduler_node()
        except (
                SaveSlurmConfigurationFileException,
                QuerySlurmctlServiceStatusException
        ):
            raise
        except Exception as e:
            logger.exception("Update queue '%s' failed.", lim_setting.name)
            if len(get_all_limitation_details(lim_setting.name)) == 0:
                raise LimitationNotExistException from e
            raise UpdateLimitationException from e
        return {"is_scheduler_node": is_scheduler_node}

    def delete_limitation(self, limitation_name: str) -> dict:
        # Check if limitation exists
        try:
            limitation = check_output(  # nosec B603 B607
                ["sacctmgr", "show", "qos", limitation_name, "format=name"]
            ).decode()
        except Exception as e:
            logger.exception("Query limitation '%s' failed.", limitation_name)
            raise QueryLimitationException from e
        if len(limitation.split('\n')) < 4:
            logger.error("Limitation name '%s' does not exist.",
                         limitation_name)
            raise LimitationNotExistException

        # Check if limitation is in use
        # By partitions
        partitions = check_output([  # nosec B603 B607
            'scontrol', 'show', 'partition'
        ]).decode()
        # By associations
        assocs = (
            check_output([  # nosec B603 B607
                'sacctmgr', 'show', 'association', 'format=qos'
            ])
            .decode()
            .split('\n')
        )

        qos_partition = re.findall(r'QoS=([^\s]+)', partitions)
        qos_assoc = [elem.strip() for elem in assocs][2:-1]
        all_qos = qos_partition + qos_assoc

        for qos in all_qos:
            if limitation_name in qos:
                logger.error(
                    "Limitation '%s' is currently in use.", limitation_name)
                raise LimitationInUseException

        # Delete limitation
        try:
            check_call([  # nosec B603 B607
                'sacctmgr', '-i', 'delete', 'qos', limitation_name
            ])
            save_slurm_conf()
            is_scheduler_node = self.is_scheduler_node()
        except (
                SaveSlurmConfigurationFileException,
                QuerySlurmctlServiceStatusException
        ):
            raise
        except Exception as e:
            logger.exception("Delete limitation '%s' failed.", limitation_name)
            raise DeleteLimitationException from e
        return {"is_scheduler_node": is_scheduler_node}

    ####################################################################
    # Scheduler Association
    ####################################################################
    def get_billing_group_qos_associations(self):
        """ Returns a list with the associations between
        account, user, queue and qos
        """
        lines = check_output(  # nosec B603 B607
            ["sacctmgr", "show", "account", "format=account,descr", "-Pn"]
        ).decode().split("\n")

        account_descr = {}
        for line in lines:
            if not line:
                continue

            name, descr = line.split("|")
            account_descr[name] = descr

        lines = check_output([  # nosec B603 B607
            "sacctmgr", "show", "assoc", "format=account,user,partition,qos", "-Pn"
        ]).decode().split("\n")

        items = []
        for line in lines:
            if not line:
                continue

            account, user, queue, qos = line.split("|")

            items.append({
                "account": {
                    "name": account,
                    "descr": account_descr.get(account, ""),
                },
                "user": user,
                "queue": queue,
                "qos": qos,
            })

        return items

    def create_association(self, new_assoc: Association) -> dict:
        # Check if account exists
        try:
            account = (
                check_output([  # nosec B603 B607
                    'sacctmgr', 'show', 'account',
                     f'account={new_assoc.account}', 'format=account', '-Pn'
                ])
                .decode()
                .split('\n')
            )[0]
        except Exception as e:
            logger.exception("Query account '%s' failed.", new_assoc.account)
            raise QueryAccountException from e

        if not account:
            # Create SLURM account for LICO billing group
            try:
                check_call(  # nosec B603 B607
                    ['sacctmgr', '-i', 'create', 'account',
                     f'name={new_assoc.account}', 'descr=lico.billing_group']
                )
            except Exception as e:
                logger.exception(
                    "Create account '%s' failed.", new_assoc.account)
                raise CreateAccountException from e

        # Create association
        qos = ','.join(new_assoc.qos)
        try:
            check_call([  # nosec B603 B607
                'sacctmgr', '-i', 'modify', 'account',
                f'name={new_assoc.account}', 'set', f'qos={qos}'
            ])
            is_scheduler_node = self.is_scheduler_node()
        except QuerySlurmctlServiceStatusException:
            raise
        except Exception as e:
            logger.exception(
                f"Create association between account='{new_assoc.account}' \
                and qos='{qos}' failed."
            )
            raise CreateAssociationException from e
        return {"is_scheduler_node": is_scheduler_node}

    def delete_association(self, account_name: str) -> dict:
        # Check if account exists
        try:
            account = (
                check_output([  # nosec B603 B607
                    'sacctmgr', 'show', 'account',
                    f'account={account_name}', 'format=account', '-Pn'
                ])
                .decode()
                .split('\n')
            )[0]
        except Exception as e:
            logger.exception("Query account '%s' failed.", account_name)
            raise QueryAccountException from e
        if not account:
            logger.error(
                "Account with name '%s' does not exist.", account_name
            )
            raise AccountNotExistException

        # Delete association between account and qos by setting qos-={current}
        try:
            # Current qos associated to account
            current = check_output([  # nosec B603 B607
                'sacctmgr','show','association', f'account={account_name}',
                 "user=''","partition=''", 'format=qos', '-Pn'
            ]).decode().split('\n')[0]
            # Delete
            check_call([  # nosec B603 B607
                'sacctmgr', '-i', 'modify', 'account', f'name={account_name}',
                 'set', f"qos-={current}"
            ])
            is_scheduler_node = self.is_scheduler_node()
        except QuerySlurmctlServiceStatusException:
            raise
        except Exception as e:
            logger.exception("Delete association '%s' failed.", account_name)
            raise DeleteAssociationException from e
        return {"is_scheduler_node": is_scheduler_node}

