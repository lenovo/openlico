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

import json
import logging
import re
from collections import defaultdict
from datetime import datetime
from os import path
from subprocess import TimeoutExpired  # nosec B404
from typing import List, Optional

from dateutil.parser import parse

from lico.scheduler.adapter.lsf.lsf_job_identity import JobIdentity
from lico.scheduler.base.exception.job_exception import (
    AcctNoFileException, CancelJobFailedException, HoldJobFailedException,
    InvalidPriorityException, JobFileNotExistException,
    QueryJobFailedException, QueryJobRawInfoFailedException,
    QueryRuntimeException, QueryUserPriorityException,
    ReleaseJobFailedException, SchedulerConnectTimeoutException,
    SchedulerRequeueJobException, ServerDownException, SetPriorityException,
    SubmitJobFailedException,
)
from lico.scheduler.base.exception.manager_exception import (
    GPUConfigurationException, QueryLicenseFeatureException,
)
from lico.scheduler.base.job.job import Job
from lico.scheduler.base.job.queue import Queue
from lico.scheduler.base.job.queue_state import QueueState
from lico.scheduler.base.scheduler import IScheduler
from lico.scheduler.utils.cmd_utils import (
    exec_oscmd, exec_oscmd_with_login, exec_oscmd_with_user,
)

from .lsf_acct_parser import query_events_by_time
from .lsf_config import SchedulerConfig
from .utils.job_parser import parse_job_info
from .utils.utils import get_job_submit_datetime

logger = logging.getLogger(__name__)


class Scheduler(IScheduler):
    def __init__(
            self,
            operator_username: str,
            config: SchedulerConfig = SchedulerConfig()
    ):
        super(Scheduler, self).__init__()
        self._operator_username = operator_username
        self._as_admin = (operator_username == 'root')
        self._config = config

    def submit_job(
            self,
            job_content: str,
            job_comment: Optional[str] = None,
            job_name: str = None
    ):
        raise NotImplementedError("submit_job")

    def submit_job_from_file(
            self,
            job_filename: str,
            job_comment: Optional[str] = None,
            job_name: str = None
    ) -> JobIdentity:

        if not path.exists(job_filename):
            raise JobFileNotExistException

        logger.debug("submit job entry")
        args = ['bsub']
        if job_name:
            args.extend(['-J', job_name])
        if job_comment:
            args.extend(['-Jd', job_comment])
        args.extend(['<', job_filename])

        rc, out, err = exec_oscmd_with_user(
            self._operator_username,
            args,
            timeout=self._config.timeout
        )
        reg = re.compile(r'^Job <(.*?)>')
        ret = reg.findall(out.decode())

        if len(ret) < 1:
            logger.error(
                "Submit job failed, job file is invalid. "
                "Error message is: %s", err.decode()
            )
            raise SubmitJobFailedException(err.decode())

        scheduler_id = ret[0]
        return JobIdentity(
            scheduler_id,
            submit_time=get_job_submit_datetime(
                scheduler_id, self._config
            )
        )

    def job_action(self, scheduler_ids, command: List[str], action: str):
        logger.debug("%s job entry, scheduler_ids: %s", action, scheduler_ids)
        if self._as_admin:
            args = ['bash', '--login', '-c'] + command
        else:
            args = ['su', '-', self._operator_username, '-c'] + command

        rc, out, err = exec_oscmd(args, self._config.timeout)
        if rc != 0:
            logger.error(
                "Failed to %s the jobs, Error message is: %s",
                action, err.decode()
            )
        status = self.batch_command_status(len(scheduler_ids),
                                           len(err.decode().splitlines()))
        return status

    def cancel_job(self, scheduler_ids) -> None:
        ids = " ".join(scheduler_ids)
        args = ['job_ids=(%s); for job_id in "${job_ids[@]}";'
                ' do bkill $job_id ;done' % ids]
        status = self.job_action(scheduler_ids, args, 'cancel')
        if status == "fail":
            raise CancelJobFailedException
        return status

    def hold_job(self, scheduler_ids) -> None:
        ids = " ".join(scheduler_ids)
        args = ['job_ids=(%s); for job_id in "${job_ids[@]}";'
                ' do bstop $job_id ;done' % ids]
        status = self.job_action(scheduler_ids, args, 'hold')
        if status == "fail":
            raise HoldJobFailedException
        return status

    def release_job(self, scheduler_ids) -> None:
        logger.debug("release_job entry")
        ids = " ".join(scheduler_ids)
        args = ['job_ids=(%s); for job_id in "${job_ids[@]}";'
                ' do bresume $job_id ;done' % ids]
        status = self.job_action(scheduler_ids, args, 'release')
        if status == "fail":
            raise ReleaseJobFailedException
        return status

    def query_job(self, job_identity: JobIdentity) -> Job:
        scheduler_id = job_identity.scheduler_id
        formatter = r"jobid job_name stat user queue job_description " \
                    r"exit_code exec_host alloc_slot run_time slots " \
                    r"avg_mem input_file output_file error_file " \
                    r"output_dir runtimelimit exec_cwd pend_reason priority "
        if self.is_gpu_new_syntax_extend():
            formatter += r"gpu_alloc "
        cmd = ["bjobs", "-o", formatter + r"delimiter=';'", "-json"]

        rc, out, err = exec_oscmd_with_login(
            ["bjobs", '-UF', scheduler_id],
            timeout=self._config.timeout
        )

        job_info_uf = [s for s in out.decode().splitlines() if s.strip() != '']
        logger.debug('Get job info: %s', job_info_uf)
        if len(job_info_uf) <= 0:
            logger.error(
                "Get job %s detail info failed, job_identity is invalid. "
                "Error message is: %s",
                scheduler_id, err.decode()
            )
            raise QueryJobFailedException(err.decode())

        cmd.extend([scheduler_id])
        rc_1, out_1, err_1 = exec_oscmd_with_login(cmd, self._config.timeout)

        detail_dict = json.loads(out_1.decode())
        info_o = {}
        for record in detail_dict.get("RECORDS", []):
            info_o = record

        job = parse_job_info(
            scheduler_id,
            {'info_uf': job_info_uf, 'info_o': info_o},
            self._config
        )
        return job

    def query_recent_jobs(self, query_memory=True) -> List[Job]:
        job_list = []
        all_jobs_info = {}

        formatter = r"jobid jobindex job_name stat user queue " \
                    r"job_description exit_code exec_host alloc_slot " \
                    r"run_time slots avg_mem input_file output_file" \
                    r" error_file output_dir runtimelimit exec_cwd " \
                    r"pend_reason priority "
        if self.is_gpu_new_syntax_extend():
            formatter += r"gpu_alloc "
        cmd = ["bjobs", "-o", formatter + r"delimiter=';'", "-json"]

        try:
            rc_0, out_0, err_0 = exec_oscmd_with_login(
                ["bjobs", "-UF", "-a", "-l", "-u", "all"],
                self._config.timeout
            )
        except TimeoutExpired:
            logger.exception('Query recent job timeout.')
            return job_list

        lines = [s for s in out_0.decode().splitlines() if s.strip() != '']

        if len(lines) < 1:
            return job_list

        scheduler_id = None
        if len(lines) > 1 and lines[0].find("Job") == 0:
            for line in lines:
                reg = re.compile(r"^Job <(.*?)>, .*")
                if reg.match(line):
                    scheduler_id = reg.search(line).groups()[0]
                    all_jobs_info[scheduler_id] = {'info_uf': []}

                if scheduler_id in all_jobs_info:
                    all_jobs_info[scheduler_id]['info_uf'].append(line)

        cmd.extend(all_jobs_info.keys())
        rc_1, out_1, err_1 = exec_oscmd_with_login(cmd, self._config.timeout)

        detail_dict = json.loads(out_1.decode())

        for record in detail_dict.get("RECORDS", []):
            jobindex = record.get('JOBINDEX')
            if jobindex == '0':
                jobid = record['JOBID']
            else:
                jobid = "{0}[{1}]".format(record['JOBID'], jobindex)
            if jobid in all_jobs_info:
                all_jobs_info[jobid]['info_o'] = record
            else:
                logger.exception(
                    'Get job info_o failed. jobid: %s, out: %s, err: %s',
                    jobid, detail_dict, err_1
                )

        for sched_id in all_jobs_info:
            try:
                job = parse_job_info(
                    sched_id, all_jobs_info[sched_id], self._config
                )
            except Exception:
                logger.exception(
                    'Parse job info failed. Scheduler id: %s.', sched_id,
                )
            else:
                job_list.append(job)

        return job_list

    def is_gpu_new_syntax_extend(self):
        configs = self.get_scheduler_config()
        new_syntax = configs.get("LSB_GPU_NEW_SYNTAX")

        if new_syntax and new_syntax.lower() == 'extend':
            return True
        else:
            return False

    def query_available_queues(self) -> List[Queue]:
        queues_list = []

        logger.debug("get all_queues entry")
        cmd_list = ['bqueues']
        if not self._as_admin:
            cmd_list.extend(['-u', self._operator_username])
        rc, out, err = exec_oscmd_with_login(
            cmd_list, self._config.timeout
        )
        lines = out.decode().splitlines()
        if len(lines) <= 1:
            return queues_list

        for line in lines:
            items = line.split()
            if len(items) > 3 and items[2].strip() == "Open:Active":
                queue = Queue(
                    name=items[0].strip(),
                    state=QueueState.UP
                )
                queues_list.append(queue)
        return queues_list

    def get_status(self) -> bool:
        try:
            rc, out, err = exec_oscmd_with_login(
                ['badmin', 'showstatus'],
                timeout=self._config.timeout
            )

            if err:
                logger.error(err.decode())
                return False
            else:
                return True

        except TimeoutExpired:
            logger.exception("Get lsf's status timeout.")
            return False

    def get_runtime(self) -> int:
        try:
            rc, out, err = exec_oscmd_with_login(
                ['badmin', 'showstatus'],
                timeout=self._config.timeout
            )
        except TimeoutExpired as e:
            raise SchedulerConnectTimeoutException from e
        if re.search(r'LSF is down', err.decode()):
            raise ServerDownException

        lines = out.decode().splitlines()
        for line in lines:
            if re.match(r'.*Latest mbatchd start.*', line):
                items = line.split(':', 1)
                boot_time = parse(items[-1].strip())
                runtime = (datetime.now() - boot_time).total_seconds()
                return int(runtime)

        logger.error("Query scheduler runtime failed. %s", err.decode())
        raise QueryRuntimeException

    def query_job_raw_info(self, job_identity: JobIdentity) -> str:
        scheduler_id = job_identity.scheduler_id

        rc, out, err = exec_oscmd_with_login(
            ["bjobs", "-l", scheduler_id],
            self._config.timeout
        )

        if err:
            logger.error(
                "Query job raw info failed, job_identity is invalid. "
                "Error message is: %s", err.decode()
            )
            raise QueryJobRawInfoFailedException(err.decode())

        return out.decode()

    def recycle_resources(self, job_identity: JobIdentity):
        pass

    def get_history_job(
            self,
            start_time_stamp: int,
            end_time_stamp: int
    ) -> List[Job]:
        if not (
                self._config.acct_file_path and
                path.exists(self._config.acct_file_path)
        ):
            logging.error('Acct file is not exist.')
            raise AcctNoFileException

        events = query_events_by_time(
            self._config.acct_file_path, start_time_stamp, end_time_stamp
        )

        return [
            event.get_acct_job() for event in events if event.get_acct_job()
        ]

    def get_scheduler_resource(self):
        configs = self.get_scheduler_config("LSF_GPU_AUTOCONFIG")
        if configs.get("LSF_GPU_AUTOCONFIG", "").lower() == "y":
            formatter = "HOST_NAME status ngpus"
        else:
            formatter = "HOST_NAME status"

        ret, out1, err = exec_oscmd_with_login(
            ["lsload", "-o", formatter],
            timeout=self._config.timeout
        )
        if err:
            logger.error(
                "Scheduler GPU configuration error."
                "Error message is: %s", err.decode()
            )
            raise GPUConfigurationException(err.decode())
        out1 = out1.decode().strip()

        nodes_dict = dict()
        for line in out1.splitlines()[1:]:
            if line.strip() == '':
                continue

            node_info = line.split()
            if len(node_info) < 2:
                logger.warning("get cluster info error!", line)
                continue

            hostname = node_info[0]
            status = node_info[1]
            gpus = 0
            if len(node_info) > 2 and node_info[2].isdigit():
                gpus = node_info[2]
            nodes_dict[hostname] = {
                "hostname": hostname,
                "state": status,
                "gres": {"gpu": {"total": gpus}}
            }

        ret, out2, err = exec_oscmd_with_login(
            [
                "lshosts", "-o",
                "HOST_NAME server maxmem nprocs ncores nthreads"
            ], timeout=self._config.timeout)
        out2 = out2.decode().strip()

        nodes = list()
        for node in out2.splitlines()[1:]:

            info = node.strip().split()
            hostname = info[0].strip()
            server = info[1].strip()
            if server == 'No':
                continue
            maxmem = info[2].strip()
            nprocs = info[3].strip()
            ncores = info[4].strip()
            nthreads = info[5].strip()

            #  Values are automatically scaled for M (MB), G (GB), and T (TB),
            #  where the default unit is M (MB).
            men_unit_dict = {
                "M": 1024,
                "G": 1024 * 1024,
                "T": 1024 * 1024 * 1024,
            }

            if re.search(r"\d", maxmem):
                try:
                    if maxmem[-1].isdigit():
                        maxmem = float(maxmem) * men_unit_dict["M"]
                    else:
                        mem = maxmem[:-1]
                        unit = maxmem[-1]
                        maxmem = float(mem) * men_unit_dict[unit]
                except ValueError:
                    logger.exception(
                        "Memory value is  not float!", info[1], info[2])

            else:
                maxmem = None
                logger.info("Parse node cpu info error!", info[1], info[2])

            if nprocs.isdigit() and ncores.isdigit() and nthreads.isdigit():
                cpu_total = int(nprocs) * int(ncores) * int(nthreads)
            else:
                cpu_total = None
                logger.info("Parse node memory info error!", info[1], info[2])

            nodes_dict[hostname].update({
                "cpu_total": cpu_total,
                "mem_total": maxmem
            })

            nodes.append(nodes_dict[hostname])

        return nodes

    def get_scheduler_config(self, *args) -> dict:
        cmd = ["badmin", "showconf", "mbd"]
        ret, out, err = exec_oscmd_with_login(
            cmd,
            timeout=self._config.timeout
        )
        out = out.decode()
        pattern = re.compile(r'^([^=]+)=([^=]+)$')
        configs = dict()
        for item in out.splitlines():
            m = pattern.match(item)
            if m and len(m.groups()) == 2:
                configs.update({m.group(1).strip(): m.group(2).strip()})

        if args:
            configs = {key: configs.get(key) for key in args}
        return configs

    def parse_scheduler_resource(self, cmd, *hostname):
        gres_dict = defaultdict(list)
        rc, out, err = exec_oscmd_with_login(
            cmd, self._config.timeout)
        if err:
            logger.error('Parse mig command failed: {0}, Error message '
                         'is: {1}'.format(' '.join(cmd), err.decode()))
            return []
        out_list = out.decode().strip().lower().splitlines()
        title_list = out_list[0].strip().split()[1:]
        title_len = len(title_list)
        host = None
        for item in out_list[1:]:
            item_list = item.strip().split()
            if len(item_list) == title_len + 1:
                if not hostname:
                    host = item_list[0]
                else:
                    if item_list[0] in hostname:
                        host = item_list[0]
                    else:
                        continue
                gres_dict[host].append(
                    dict(zip(title_list, item_list[1:]))
                )
            elif len(item_list) == title_len and host:
                gres_dict[host].append(
                    dict(zip(title_list, item_list))
                )
        return gres_dict

    def _get_gres(self):
        gpu_command = ['lshosts', '-gpu', '-w']
        host_gpu_dict = self.parse_scheduler_resource(gpu_command)
        gres_dict = defaultdict(lambda: defaultdict(int))
        mig_support = False
        for host, gpu_list in host_gpu_dict.items():
            for gpu_info in gpu_list:
                mig = gpu_info.get('mig', '').lower()
                if mig == 'y' and not mig_support:
                    mig_support = True
                gres_dict[host]['gpu_total'] += 1

        if not mig_support:
            return gres_dict, {}
        mig_command = ['lshosts', '-gpu', '-mig', '-w']
        mig_dict = self.parse_scheduler_resource(mig_command)
        """
            mig_dict example for command: lshosts -gpu -mig -w
            {
                'head': [
                    {
                        'gpu_id': '0',
                        'gpu_model': 'UnknownNVIDIAA100_PCIE_40GB',
                        'gpu_driver': '470.82.01',
                        'gpu_factor': '8.0',
                        'numa_id': '1',
                        'vendor': 'Nvidia',
                        'devid': '0',
                        'gid': '1',
                        'cid': '0',
                        'inst_name': '2c.4g.20gb'
                    },
                    ...
                ],
                ...
            }
        """

        """
        gres_dict example for command: lshost -gpu -w
            {
                'head': {
                    'gpu_total': 3
                },
                ...
            }
        """
        return gres_dict, mig_dict

    def get_gres_type(self) -> dict:
        gres_type_dict = dict()
        configs = self.get_scheduler_config(
            "LSF_GPU_AUTOCONFIG", "LSF_MANAGE_MIG"
        )
        gpu_config = configs.get("LSF_GPU_AUTOCONFIG")
        if gpu_config is None or gpu_config.lower() != "y":
            return gres_type_dict
        lsf_manage_mig = configs.get("LSF_MANAGE_MIG")
        if lsf_manage_mig is None:
            return gres_type_dict

        if lsf_manage_mig.lower() == 'y':
            # TODO: finish dynamic management for mig
            return gres_type_dict
        elif lsf_manage_mig.lower() == 'n':
            gres_dict, mig_dict = self._get_gres()
            for hostname, gpu_info in gres_dict.items():
                host_gpu_total = gres_dict[hostname]['gpu_total']
                if not host_gpu_total:
                    continue
                mig_gpu_list = list()
                gres_type_dict[hostname] = defaultdict(int)
                for item_dict in mig_dict.get(hostname, []):
                    inst_name = item_dict.get('inst_name', '')
                    if not inst_name or inst_name == '-':
                        logger.info("Parse inst_name is empty!")
                        continue
                    gres_type_dict[hostname][
                        self._parse_mig_type(inst_name)] += 1
                    mig_gpu_list.append(item_dict.get('gpu_id'))
                mig_gpu_total = len(set(mig_gpu_list))
                if mig_gpu_total < host_gpu_total:
                    gres_type_dict[hostname][''] = \
                        host_gpu_total - mig_gpu_total

        """
        gres_type_dict example:
            {
                "head": {"2/2": 1, "4/2": 2},
                "c1": {"1/1": 2},
                ...
            }
        """
        return gres_type_dict

    @staticmethod
    def _parse_mig_type(inst_name):
        """
        inst_name format example:
            2c.4g.20gb ----> return 4/2
            2g.10gb -----> return 2/2
        """

        ci = gi = None
        for res in inst_name.split('.'):
            if res.endswith('c'):
                ci = res[:-1]
            elif res.endswith('g'):
                gi = res[:-1]
        if ci is None:
            ci = gi
        return '{gi}/{ci}'.format(gi=gi, ci=ci)

    # provide license feature
    def get_license_feature(self) -> list:
        cmd = ["blstat"]
        license_feature = []
        ret, out, err = exec_oscmd_with_login(
            cmd,
            timeout=self._config.timeout
        )
        if err:
            logger.error(
                "Get license feature error."
                "Error message is: %s", err.decode()
            )
            raise QueryLicenseFeatureException(err.decode())
        out = out.decode().strip()
        pattern_feature = re.compile(r':(.*?)@')
        pattern_total = re.compile(r'TOTAL_ALLOC:(.*?)TOTAL_USE')
        pattern_used = re.compile(r'TOTAL_USE:(.*?)OTHERS')
        for item in out.split('FEATURE'):
            if item:
                feature = pattern_feature.search(item)
                total = pattern_total.search(item)
                used = pattern_used.search(item)
                license_feature.append(
                    {"feature": feature.group(1).strip() if feature else None,
                     "total": int(total.group(1).strip()) if total else None,
                     "used": int(used.group(1).strip()) if used else None}
                )
        return license_feature
        # example : [{'feature': 'cfd_preppost', 'total': 4, 'used': 0},
        # {'feature': 'cfd_base', 'total': 4, 'used': 0}]

    def get_running_jobs_cmd(self, *args):
        return 'bjobs -UF -r -u all'.split()

    def get_job_pidlist(self, *args):
        job_pid_dict = dict()
        hostname = args[1]
        job_out = args[0]
        split_str = "-" * 78
        data = job_out.strip().split(split_str)

        for item in data:
            jobid_pattern = re.compile(r"Job <([^<|^>]+)>, Job Name ")
            pattern = jobid_pattern.search(item.strip())
            jobid = pattern.groups()[0] if pattern else None

            res_pattern = re.compile(r"Resource usage collected.([^\n]*)")
            pattern = res_pattern.search(item)
            res = pattern.groups()[0] if pattern else ""

            if "HOST" in res:
                res = res.split("HOST:")
                for info in res[1:]:
                    host_pattern = re.compile(r"([^;]+);")
                    pattern = host_pattern.match(info.strip())
                    host = pattern.groups()[0] if pattern else None
                    if host != hostname:
                        continue
                    pids_pattern = re.compile(r"PIDs:([^;]*);")
                    pattern = pids_pattern.search(info)
                    pids = pattern.groups()[0] if pattern else ""
                    pids = pids.strip().split(" ")
                    job_pid_dict[jobid] = pids
            else:
                task_on_host_pattern = re.compile(
                    r"Started\s\d+\sTask\(s\)\son\sHost\(s\)\s([^,]*)", re.I)
                pattern = task_on_host_pattern.search(item.strip())
                if not pattern:
                    continue
                hosts = pattern.groups()[0]
                host_list = re.findall(r"<(\d+\*)?(.+)>", hosts)
                if not host_list or \
                        host_list[0][1].lower() != hostname.lower():
                    continue
                pids_pattern = re.compile("PIDs:[^;]+")
                pids = pids_pattern.findall(res)
                pid_all = []
                for item in pids:
                    pid_pattern = re.compile(r"\d+")
                    pid_list = pid_pattern.findall(item)
                    pid_all += pid_list
                job_pid_dict[jobid] = pid_all

        return job_pid_dict

    def get_parse_job_pidlist_funs(self):
        return [
            self.get_running_jobs_cmd,
            self.get_job_pidlist
        ]

    def _query_user_priority(self):
        logger.debug("query the maximum user priority")
        args = ["bparams", "-a", "|", "grep", "MAX_USER_PRIORITY", "|",
                "awk", "'", "{", "print", "$3", "}", "'"]
        rc, out, err = exec_oscmd_with_login(
            args,
            timeout=self._config.timeout
        )
        if err:
            logger.error(
                "query the maximum user priority failed, "
                "Error message is: %s", err.decode()
            )
            raise QueryUserPriorityException(err.decode())
        return out.decode().strip()

    def get_priority_value(self):
        priority_max = self._query_user_priority()
        priority_dict = {"priority_min": "1",
                         "priority_max": priority_max}
        return priority_dict

    def update_job_priority(self, scheduler_ids, priority_value):
        logger.debug("Update job priority, scheduler_ids: %s" % scheduler_ids)
        if int(priority_value) > int(self._query_user_priority()) or int(
                priority_value) < 1:
            raise InvalidPriorityException
        ids = " ".join(scheduler_ids)
        args = ['job_ids=(%s); for job_id in "${job_ids[@]}";'
                ' do bmod -sp %s $job_id ;done' % (ids, priority_value)]
        status = self.job_action(scheduler_ids, args, 'priority')
        if status == "fail":
            raise SetPriorityException
        return status

    def requeue_job(self, scheduler_ids):
        logger.debug("requeue_job entry")
        ids = " ".join(scheduler_ids)
        args = ['job_ids=(%s); for job_id in "${job_ids[@]}";'
                ' do brequeue $job_id ;done' % ids]
        status = self.job_action(scheduler_ids, args, 'requeue')
        if status == "fail":
            raise SchedulerRequeueJobException
        return status
