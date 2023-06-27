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
import os
import re
from collections import defaultdict
from subprocess import TimeoutExpired
from typing import List, Optional

from dateutil.parser import parse

from lico.scheduler.base.exception.job_exception import (
    CancelJobFailedException, JobFileNotExistException,
    QueryJobFailedException, QueryJobRawInfoFailedException,
    QueryRuntimeException, SchedulerConnectTimeoutException,
    SubmitJobFailedException,
)
from lico.scheduler.base.exception.manager_exception import (
    QueryLicenseFeatureException,
)
from lico.scheduler.base.job.job import Job
from lico.scheduler.base.job.queue import Queue
from lico.scheduler.base.scheduler import IScheduler
from lico.scheduler.utils.cmd_utils import (
    exec_oscmd, exec_oscmd_with_login, exec_oscmd_with_user,
)

from .slurm_acct_parser import query_events_by_time
from .slurm_config import SchedulerConfig
from .slurm_job_identity import JobIdentity
from .utils.job_parser import (
    get_job_alter_id, get_job_submit_datetime, parse_job_info,
)
from .utils.queue_parser import ignore_non_slurm_output, parse_queue_info

logger = logging.getLogger(__name__)


class Scheduler(IScheduler):
    def __init__(
            self,
            operator_username: str,
            config: SchedulerConfig = SchedulerConfig()
    ):
        self._operator_username = operator_username
        self._as_admin = (operator_username == 'root')
        self._config = config

    def submit_job(
            self,
            job_content: str,
            job_comment: Optional[str] = None,
            job_name: Optional[str] = None
    ) -> JobIdentity:
        raise NotImplementedError("submit_job")

    def submit_job_from_file(
            self,
            job_filename: str,
            job_comment: Optional[str] = None,
            job_name: Optional[str] = None
    ) -> JobIdentity:
        logger.debug("submit_job_from_file entry")
        if not os.path.isfile(job_filename):
            raise JobFileNotExistException
        args = ['sbatch']
        if job_name is not None:
            args.extend(['-J', job_name])
        if job_comment is not None:
            args.extend(['--comment', job_comment])
        args.append(job_filename)

        rc, out, err = exec_oscmd_with_user(
            self._operator_username, args, timeout=self._config.timeout
        )
        # Some envrionment has login welcome message
        # m = re.match(r'^.+?(?P<job_id>[\d_]+)$', out.strip().decode())
        m = re.match(
            r'^[\s\S]+?batch job (?P<job_id>[\d_]+)$',
            out.strip().decode()
        )
        if m is not None:
            jobid = m.groupdict()['job_id']
            return JobIdentity(
                scheduler_id=str(jobid),
                submit_time=get_job_submit_datetime(
                    jobid, self._config.timeout
                )
            )
        else:
            logger.error("Submit job failed: no job id is returned "
                         "Error message is: %s", err.decode())
            raise SubmitJobFailedException(err.decode())

    def cancel_job(self, job_identity: JobIdentity) -> None:
        jobid = job_identity.scheduler_id
        jobid = get_job_alter_id(jobid, self._config.timeout)
        logger.debug("cancel_job entry")
        if self._as_admin:
            rc, out, err = exec_oscmd(
                ['scancel', jobid],
                self._config.timeout
            )
        else:
            rc, out, err = exec_oscmd_with_user(
                self._operator_username,
                ['scancel', jobid],
                self._config.timeout
            )
        if rc != 0:
            logger.error(
                "Cancel job %s failed, job_identity is invalid. "
                "Error message is: %s", jobid, err.decode()
            )
            raise CancelJobFailedException(err.decode())

    def query_job(self, job_identity: JobIdentity) -> Job:
        jobid = job_identity.scheduler_id
        args = ["scontrol", "show", "jobs", jobid]
        rc, out, err = exec_oscmd(args, self._config.timeout)
        job_info = [s for s in out.decode().splitlines() if s.strip() != '']
        if len(job_info) <= 0:
            logger.error(
                "Get job %s detail info failed, job_identity is invalid. "
                "Error message is: %s",
                jobid, err.decode()
            )
            raise QueryJobFailedException(err.decode())
        job = parse_job_info(
            jobid=jobid,
            job_info=job_info,
            config=self._config
        )
        return job

    def query_recent_jobs(self, query_memory=True) -> List[Job]:
        all_job_status_info = {}
        jobs_list = []
        jobid = None
        rc, out, err = exec_oscmd(
            ["scontrol", "show", "jobs"], self._config.timeout
        )
        lines = out.decode().splitlines()
        if len(lines) < 1:
            return jobs_list
        for line in lines:
            if line.find("JobId") == 0:
                jobid = line.split()[0].split("=")[1].strip()
                all_job_status_info[jobid] = {'info': []}
            if jobid in all_job_status_info:
                all_job_status_info[jobid]['info'].append(line)

        for jobid in all_job_status_info:
            try:
                job = parse_job_info(
                    jobid=jobid,
                    job_info=all_job_status_info[jobid]["info"],
                    config=self._config,
                    query_memory=query_memory
                )
            except Exception:
                logger.exception(
                    'Parse job info failed. Scheduler id: %s.', jobid,
                )
            else:
                jobs_list.append(job)
        return jobs_list

    def query_available_queues(self) -> List[Queue]:
        logger.debug("query_available_queues entry")

        sinfo_cmd_list = [
            "sinfo",
            "-O", "partition:250,nodes,gres:{0},gresused:{0},cpusstate:{0}".
            format(self._config.cmd_out_places)
        ]
        partition_cmd_list = ['scontrol', 'show', 'partition', '-o']

        if self._as_admin:
            sinfo_rc, sinfo_out, sinfo_err = exec_oscmd(
                args=sinfo_cmd_list,
                timeout=self._config.timeout
            )
            partition_rc, partition_out, partition_err = exec_oscmd(
                args=partition_cmd_list,
                timeout=self._config.timeout
            )
        else:
            sinfo_rc, sinfo_out, sinfo_err = exec_oscmd_with_user(
                user=self._operator_username,
                args=sinfo_cmd_list,
                timeout=self._config.timeout
            )
            partition_rc, partition_out, partition_err = exec_oscmd_with_user(
                user=self._operator_username,
                args=partition_cmd_list,
                timeout=self._config.timeout
            )

        sinfo_lines = ignore_non_slurm_output(sinfo_out, 'PARTITION')
        partition_lines = ignore_non_slurm_output(
            partition_out, 'PartitionName')

        return parse_queue_info(sinfo_lines, partition_lines, self._config)

    def get_status(self) -> bool:
        rc, out, err = exec_oscmd(["scontrol", "ping"], self._config.timeout)
        lines = out.splitlines()
        if len(lines) < 1:
            return False

        for line in lines:
            m = re.match(
                r'^Slurmctld\((?:primary|backup|primary/backup)\) '
                r'at .+ (?:is|are) (UP|DOWN)/?(UP|DOWN)?$',
                line.decode()
            )

            if m is not None and 'UP' in m.groups():
                return True
            else:
                continue

        return False

    def get_runtime(self) -> int:
        try:
            rc, out, err = exec_oscmd_with_login(
                ['scontrol', 'show', 'config'],
                timeout=self._config.timeout
            )
        except TimeoutExpired as e:
            raise SchedulerConnectTimeoutException from e
        if err and not out:
            logger.error("Query scheduler runtime failed. %s", err.decode())
            raise QueryRuntimeException

        lines = out.decode().splitlines()
        slurmctld_time = boot_time = None
        for line in lines:
            result = re.match(r'^Configuration data as of (.*)', line)
            if result:
                slurmctld_time = parse(result.group(1))
            elif re.match(r'^BOOT_TIME.*=.*', line):
                boot_time = parse(line.split()[-1])
        if all([boot_time, slurmctld_time]):
            runtime = (slurmctld_time - boot_time).total_seconds()
            return int(runtime)

        logger.error("Query scheduler runtime failed. %s", err.decode())
        raise QueryRuntimeException

    def query_job_raw_info(self, job_identity: JobIdentity) -> str:
        jobid = job_identity.scheduler_id
        args = ["scontrol", "show", "jobs", jobid]
        rc, out, err = exec_oscmd(args, self._config.timeout)
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
        events = query_events_by_time(
            start_time_stamp, end_time_stamp
        )
        history_job = [
            event.get_acct_job() for event in events if event.get_acct_job()
        ]

        return history_job

    def get_scheduler_resource(self):
        rc, out, err = exec_oscmd(
            ["scontrol", "show", "node"], self._config.timeout
        )
        out = out.decode().strip().split("\n\n")

        nodeName_pattern = re.compile(r"NodeName=([^\s]+)")
        cpuTot_pattern = re.compile(r"CPUTot=([\d]+)")
        realMemory_pattern = re.compile(r"RealMemory=([\d]+)")
        state_pattern = re.compile(r"State=([^\s]+)")
        gres_pattern = re.compile(r"Gres=([^\n]+)")

        nodes = []
        for node in out:
            if nodeName_pattern.search(node):
                nodename = nodeName_pattern.search(node).group(1)
            else:
                logger.info(
                    "The node data did not resolve the NodeName: ", node)
                continue

            gres_count = {}  # count gres num
            gres_total = {}  # the final quantity
            if gres_pattern.search(node):
                gres = gres_pattern.search(node).group(1)
                for item in gres.strip().split(","):
                    if item.startswith("gpu"):
                        gres_data = item.split(":")
                        if len(gres_data) == 2:
                            gres_total[gres_data[0]] = {
                                "total": int(gres_data[-1])
                            }
                        elif len(gres_data) > 2:
                            if gres_data[0] in gres_count:
                                gres_count[gres_data[0]]["total"] += int(
                                    gres_data[-1])
                            else:
                                gres_count[gres_data[0]] = {
                                    "total": int(gres_data[-1])
                                }

                gres_count.update(gres_total)

            mem_total = None
            DEFAULT_RM = 1
            if realMemory_pattern.search(node):
                if DEFAULT_RM != int(realMemory_pattern.search(node).group(1)):
                    mem_total = int(
                        realMemory_pattern.search(node).group(1)
                    ) * 1024

            nodes.append({
                "hostname": nodename,
                "cpu_total": cpuTot_pattern.search(node).group(
                    1) if cpuTot_pattern.search(node) else None,
                "mem_total": mem_total,
                "state": state_pattern.search(node).group(
                    1) if state_pattern.search(node) else None,
                "gres": gres_count
            })

        return nodes

    def get_scheduler_config(self, *args) -> dict:
        pass

    def parse_scheduler_resource(self, command, *hostname):
        nodes_dict = defaultdict(list)
        if hostname:
            command = command.append(','.join(hostname))
        rc, out, err = exec_oscmd(
            command, self._config.timeout
        )
        if err:
            logger.error("Get node detail info failed. "
                         "Error message is {}".format(err.decode()))
            return dict(nodes_dict)
        out = out.decode().strip().split("\n\n")
        nodeName_pattern = re.compile(r"NodeName=([^\s]+)")
        pattern = re.compile(
            r"(CfgTRES=|AllocTRES=|Reason=|Comment=|OS=|"
            r"AvailableFeatures=|ActiveFeatures=|Partitions=)"
        )
        for node_info in out:
            if nodeName_pattern.search(node_info):
                nodename = nodeName_pattern.search(node_info).group(1)
            else:
                logger.info(
                    "The node data did not resolve the NodeName: ", node_info)
                continue
            node_dict = dict()
            for row_info in node_info.split('\n'):
                row = row_info.strip()
                if pattern.search(row):
                    key, value = row.split('=', 1)
                    node_dict[key] = value
                    continue
                for item in row.split():
                    key, value = item.split('=')
                    node_dict[key] = value
            if node_dict:
                nodes_dict[nodename].append(node_dict)

        """
        nodes_dict for example:
        {
            'head': [
                {
                    'NodeName': 'head',
                    'Arch': 'x86_64',
                    'CPUTot': '64',
                    'CfgTRES': 'cpu=64,mem=700000M,billing=64,gres/gpu=2',
                    'Gres': 'gpu:3g.20gb:1,gpu:2g.10gb:2'
                    ...
                }
            ],
            ...
        }
        """
        return dict(nodes_dict)

    def get_gres_type(self) -> dict:
        gres_dict = defaultdict(dict)
        cmd = ["scontrol", "show", "node"]
        for host, detail in self.parse_scheduler_resource(cmd).items():
            if not detail:
                continue
            gres = detail[0].get('Gres', '')
            if not gres:
                continue
            for item in gres.split(','):
                gres_list = item.split(":")
                if len(gres_list) == 2:
                    gres_dict[host][''] = int(gres_list[-1])
                elif len(gres_list) == 3:
                    gres_data = item.rsplit(":", 1)
                    gres_dict[host][gres_data[0]] = int(gres_data[-1])
        """
        gres_dict example:
        {
            "head": {"gpu:3g.20gb": 1, "gpu:2g.10gb": 2},
            "c1": {"": 2},
            ...
        }
        """
        return dict(gres_dict)

    def get_license_feature(self) -> dict:
        licenseName_pattern = re.compile(r"LicenseName=([^\s]+)")
        total_pattern = re.compile(r"Total=([\d]+)")
        used_pattern = re.compile(r"Used=([\d]+)")

        rc, out, err = exec_oscmd(
            ["scontrol", "show", "license", "-o"], self._config.timeout
        )
        if rc != 0:
            logger.error(
                "Fail to get license feature. "
                "Error message is: %s", err.decode()
            )
            raise QueryLicenseFeatureException(err.decode())
        out = out.decode().strip().splitlines()

        licenses = []
        for lic in out:
            # No license configured in Slurm
            if not lic.startswith("LicenseName="):
                return licenses
            license = licenseName_pattern.search(lic)
            total = total_pattern.search(lic)
            used = used_pattern.search(lic)
            licenses.append(
                {
                    "feature": license.group(1) if license else None,
                    "total": total.group(1) if total else None,
                    "used": used.group(1) if used else None
                }
            )
        """
        licenses example:
        [
            {
                "feature": "fea",
                "total": 100,
                "used": 10
            },
            ...
        ]
        """
        return licenses

    # def get_job_pidlist(self, conn):
    #     cmd = ["scontrol", "listpids"]
    #     out = conn.run(cmd).stdout
    #     data = out.splitlines()
    #     """
    #     PID      JOBID    STEPID   LOCALID GLOBALID
    #     -1       13073    extern   0       0
    #     3913206  13073    extern   -       -
    #     3913212  13073    batch    0       0
    #     3913222  13073    batch    -       -
    #     3913223  13073    batch    -       -
    #     3913224  13073    batch    -       -
    #     """
    #     job_pids = defaultdict(list)
    #     for item in data[1:]:
    #         info = item.split()
    #         job_pids[info[1]].append(info[0])
    #     return job_pids
    #
    def get_job_pidlist_cmd(self, *args):
        return ["scontrol", "listpids"]

    def parse_job_pidlist(self, *args):
        data = args[0].splitlines()
        """
        PID      JOBID    STEPID   LOCALID GLOBALID
        -1       13073    extern   0       0
        3913206  13073    extern   -       -
        3913212  13073    batch    0       0
        3913222  13073    batch    -       -
        3913223  13073    batch    -       -
        3913224  13073    batch    -       -
        """
        job_pids = defaultdict(list)
        for item in data[1:]:
            info = item.split()
            job_pids[info[1]].append(info[0])
        return job_pids

    def get_parse_job_pidlist_funs(self):
        return [
            self.get_job_pidlist_cmd,
            self.parse_job_pidlist
        ]
