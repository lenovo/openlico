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
import os
import re
import socket
from collections import defaultdict
from typing import List, Optional

from lico.scheduler.base.exception.job_exception import (
    CancelJobFailedException, InvalidPriorityException,
    JobFileNotExistException, QueryJobFailedException,
    QueryJobRawInfoFailedException, QueryRuntimeException,
    SchedulerNotWorkingException, SubmitJobFailedException,
)
from lico.scheduler.base.job.job import Job
from lico.scheduler.base.job.queue import Queue
from lico.scheduler.base.job.queue_state import QueueState
from lico.scheduler.base.scheduler import IScheduler
from lico.scheduler.utils.cmd_utils import (
    exec_oscmd, exec_oscmd_with_login, exec_oscmd_with_user,
)

from .pbs_config import SchedulerConfig
from .pbs_job_identity import JobIdentity
from .utils.job_parser import convert_string_to_bytes, parse_job_info
from .utils.utils import get_job_query_data, get_job_submit_datetime

logger = logging.getLogger(__name__)


class Scheduler(IScheduler):
    def __init__(
            self,
            operator_username: str,
            config: SchedulerConfig = SchedulerConfig()
    ):
        self._operator_username = operator_username
        self._as_admin = (operator_username == "root")
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
            job_name: Optional[str] = None,
            job_comment: Optional[str] = None,
    ) -> JobIdentity:
        logger.debug("submit_job_from_file entry")
        if not os.path.isfile(job_filename):
            raise JobFileNotExistException

        work_dir = os.path.dirname(job_filename)
        args = ['cd', work_dir, ';', 'qsub']
        if job_name is not None:
            args.extend(['-N', job_name])
        if job_comment is not None:
            args.extend(['-v', f'LiCO_JOB_ID={job_comment}'])

        args.append(job_filename)

        rc, out, err = exec_oscmd_with_user(
            self._operator_username, args, timeout=self._config.timeout
        )
        # stdout should be the job id, query the job to return the
        # proper job identity
        scheduler_id = out.decode("utf8").strip()
        if not scheduler_id or not scheduler_id.split('.')[0].isdigit():
            raise SubmitJobFailedException
        return JobIdentity(
            scheduler_id,
            submit_time=get_job_submit_datetime(
                scheduler_id, self._config
            )
        )

    def cancel_job(self, job_identity: JobIdentity) -> None:
        scheduler_id = job_identity.scheduler_id

        logger.debug("cancel job entry")
        args = (['qdel', scheduler_id], self._config.timeout)
        if self._as_admin:
            rc, out, err = exec_oscmd_with_login(*args)
        else:
            rc, out, err = exec_oscmd_with_user(self._operator_username, *args)

        if rc == 0 or b'Job has finished' in out:
            return

        logger.error(
            "Cancel job %s failed, job_identity is invalid. "
            "Error message is: %s", scheduler_id, err.decode()
        )
        raise CancelJobFailedException(err.decode())

    def query_job(self, job_identity: JobIdentity) -> Job:
        jobid = job_identity.scheduler_id
        args = ["qstat", "-xf", "-F", "json", jobid]
        rc, out, err = exec_oscmd_with_login(args, self._config.timeout)
        try:
            data = json.loads(out)
        except (json.JSONDecodeError, TypeError) as exc:
            logger.error(
                f"Get job {jobid} detail info failed, job_identity is invalid."
                f"Error message is: {exc}"
            )
            raise QueryJobFailedException(str(exc))

        job = parse_job_info(
            jobid=jobid.split('.', 1)[0],
            job_info=data["Jobs"][jobid],
            config=self._config
        )
        return job

    def query_recent_jobs(self, query_memory=True) -> List[Job]:
        cmd = ["qstat", "-xf", "-F", "json"]
        data = get_job_query_data(cmd, self._config.timeout)

        jobs = []
        array_jobs = {}  # {'123[]': <submit_host>}

        for jobid, job_info in data.get("Jobs", {}).items():
            if '[]' in jobid:
                array_jobs[jobid.split('.', 1)[0]] = job_info['Submit_Host']
            else:
                job = parse_job_info(
                    jobid=jobid.split('.', 1)[0],
                    job_info=job_info,
                    config=self._config
                )
                jobs.append(job)

        # flatten array jobs
        if array_jobs:
            cmd.append('-t')
            cmd.extend(array_jobs.keys())

            arr_data = get_job_query_data(cmd, self._config.timeout)
            for jobid, job_info in arr_data.get("Jobs", {}).items():
                if '[]' not in jobid:

                    arr_key = '{0}[]'.format(jobid.split('[')[0])
                    job_info['Submit_Host'] = array_jobs[arr_key]

                    job = parse_job_info(
                        jobid=jobid.split('.', 1)[0],
                        job_info=job_info,
                        config=self._config
                    )
                    jobs.append(job)

        return jobs

    def query_available_queues(self) -> List[Queue]:
        cmd = ["qstat", "-Qf", "-F", "json"]
        rc, out, err = exec_oscmd_with_login(cmd, self._config.timeout)
        try:
            data = json.loads(out)
        except (json.JSONDecodeError, Exception) as exc:
            logger.error(f"There was an error fetching the available queues:"
                         f" {exc}")
            raise QueryJobFailedException(str(exc))

        queues = []
        for name, qdata in data['Queue'].items():
            # compute state
            enabled = qdata.get('enabled') == 'True'
            started = qdata.get('started') == 'True'
            if enabled and started:
                state = QueueState.UP
            elif not enabled:
                state = QueueState.INACTIVE
            elif enabled and not started:
                state = QueueState.DOWN
            else:
                state = QueueState.DRAIN

            # if 'resources_default' in qdata:
            #     resource_list = get_resource(qdata['resources_default'])
            # elif 'resources_assigned' in qdata:
            #     resource_list = get_resource(qdata['resources_assigned'])
            # else:
            #     resource_list = []

            queues.append(Queue(
                name=name,
                state=state,
                resource_list=[]
            ))

        return queues

    _server_status = None

    @property
    def server_status(self):
        if self._server_status is None:
            _, out, _ = exec_oscmd_with_login(
                ["qstat", "-B"], self._config.timeout
            )
            for line in out.decode("utf8").split("\n"):
                if line.strip().endswith("Active"):
                    bits = line.split()
                    server = bits[0]
                    self._server_status = server, True
                    return self._server_status
            self._server_status = None, False
        return self._server_status

    def get_status(self) -> bool:
        _, active = self.server_status
        return active

    def get_runtime(self) -> int:
        cmd = self.get_ssh_cmd(["/etc/init.d/pbs", "status"])

        """
        out value:
            pbs_server is pid 2535814
            pbs_mom is pid 2534381
            pbs_sched is pid 2534395
            pbs_comm is 2534370
        """

        _, out, error = exec_oscmd(cmd, self._config.timeout)
        if error:
            logger.error(
                "Query scheduler status failed for PBS. "
                "Error message is: %s", error.decode()
            )
            raise SchedulerNotWorkingException

        # get pbs_server process id
        pbs_server_pid = ''
        for out_line in out.decode().split('\n'):
            if 'pbs_server' in out_line:
                pbs_server_pid = out_line.strip().split()[-1]
                break
        if not pbs_server_pid:
            server_node, active = self.server_status
            if not active:
                logger.warning(
                    'The pbs server is not active on node {0}'.format(
                        server_node))
                return 0
            logger.warning('Not query pbs_server process on node {0}'.format(
                server_node))
            return 0

        # get runtime for pbs_server process
        get_etime_cmd = self.get_ssh_cmd(
            ["ps", "-p", pbs_server_pid, "-ho", "etimes"])
        rc, etime, err = exec_oscmd(get_etime_cmd, self._config.timeout)
        if err or not etime:
            logger.error(
                "Query scheduler runtime failed for PBS. "
                "Error message is: %s", error.decode()
            )
            raise QueryRuntimeException
        return int(etime.decode().strip())

    def get_ssh_cmd(self, cmd):
        server, _ = self.server_status
        if socket.gethostname() != server:
            cmd = ["ssh", f"root@{server}"] + cmd
        return cmd

    def query_job_raw_info(self, job_identity: JobIdentity) -> str:
        jobid = job_identity.scheduler_id
        args = ["qstat", "-xf", jobid]
        rc, out, err = exec_oscmd_with_login(args, self._config.timeout)
        if err:
            logger.error(
                "Query job raw info failed, job_identity is invalid. "
                "Error message is: %s", err.decode()
            )
            raise QueryJobRawInfoFailedException(err.decode())
        return out.decode()

    def get_history_job(self, *a, **kw):
        pass

    def recycle_resources(self, *a, **kw):
        pass

    def get_scheduler_resource(self):
        cmd = self.get_ssh_cmd(["pbsnodes", "-a", "-F", "json"])
        _, out, _ = exec_oscmd_with_login(cmd, self._config.timeout)

        try:
            data = json.loads(out)
        except Exception as exc:
            logger.debug(exc)
            data = {}

        nodes = []
        for node in data.get("nodes", {}).values():
            ngpus = str(node["resources_available"].get("ngpus", 0))
            nodes.append({
                "hostname": node["resources_available"]["host"],
                "cpu_total": node["resources_available"]["ncpus"],
                "mem_total": convert_string_to_bytes(
                    node["resources_available"]["mem"]) / 1024,  # KB
                "state": node["state"],
                "gres": {
                    "gpu": {
                        "total": int(ngpus) if ngpus.isdigit() else 0
                    },
                },
            })
        return nodes

    def get_scheduler_config(self, *args) -> dict:
        pass

    def get_gres_type(self) -> dict:
        pass

    def get_license_feature(self) -> list:
        pass

    def get_job_id_cmd(self, *args):
        return ['qstat', '-rftn']

    def get_job_object(self, jobid_out):
        job_object = dict()
        pattern_jobid = re.compile(r'([\d]+)\.')
        pattern_jobid_arr = re.compile(r'([\d]+\[[\d]+\])\.')
        content_object = jobid_out.split('\n')

        for index, value in enumerate(content_object):
            job_id = pattern_jobid.findall(value)
            job_id_arr = pattern_jobid_arr.findall(value)
            if job_id:
                host_obect = content_object[index + 1].strip().split('+')
                host_list = set([i.split('/')[0] for i in host_obect])
                job_object[job_id[0]] = list(host_list)
                # host_list:['c2', 'c1']
            elif job_id_arr:
                host_obect = content_object[index + 1].strip().split('+')
                host_list = set([i.split('/')[0] for i in host_obect])
                job_object[job_id_arr[0]] = list(host_list)
        return job_object

    def parse_jobid_and_server_name(self, *args):
        jobid_out = args[0]
        hostname = args[1]
        server_object = re.search(r'-----\n(.*?) ', jobid_out).group(1)
        server_name = '.' + server_object.split('.')[-1]  # .c1
        # Get the jobid of the current node
        job_id = []
        job_object = self.get_job_object(jobid_out)
        # job_object:{'3113': ['c2', 'c1'], '3115': ['c1']}
        for key, value in job_object.items():
            if hostname in value:
                job_id.append(key)

        return {
            "server_name": server_name,
            "job_id": job_id
        }

    def get_get_running_jobs_cmd(self, *args):
        result = args[0]
        get_running_jobs_cmd = "printjob -a {0} | grep -E 'parentjob|sid'"
        return get_running_jobs_cmd.format(
            ' '.join([i for i in result[0]["job_id"]])
        ).split()

    def get_pid_sid_cmd(self, *args):
        sid_jobid_dict = args[0][1]
        cmd = "ps -s {} -o pid,sid --no-header;"
        return cmd.format(",".join(sid_jobid_dict.keys())).split()

    def get_sid_jobid_dict(self, *args):
        server_name = args[2][0]["server_name"]
        pattern_job_sid = re.compile(
            f'\tparentjobid:\t(.*?){server_name}\n\tsid:\t\t(.*?)\n')
        # get sid of all job
        job_out = args[0]
        # format of job_sid_group like [(job_id, job_sid),]
        job_sid_group = re.findall(pattern_job_sid, job_out)

        sid_jobid_dict = dict()
        for job_id, job_sid in job_sid_group:
            if '-' not in job_sid:
                sid_jobid_dict[job_sid] = job_id
        return sid_jobid_dict

    def get_job_pidlist(self, *args):
        sid_jobid_dict = args[2][1]

        sid_pids = defaultdict(list)
        for item in args[0].splitlines():
            pid, sid = item.split()
            sid_pids[sid].append(pid)

        job_pid_dict = defaultdict(list)
        for sid, jobid in sid_jobid_dict.items():
            job_pid_dict[jobid] += sid_pids[sid]

        return job_pid_dict

    def get_parse_job_pidlist_funs(self):
        return [
            self.get_job_id_cmd,
            self.parse_jobid_and_server_name,
            self.get_get_running_jobs_cmd,
            self.get_sid_jobid_dict,
            self.get_pid_sid_cmd,
            self.get_job_pidlist
        ]

    def get_priority_value(self):
        priority_dict = {"priority_min": "-1024", "priority_max": "1023"}
        return priority_dict

    def update_job_priority(self, scheduler_ids, priority_value):
        logger.debug("Update job priority, scheduler_ids: %s" % scheduler_ids)
        if int(priority_value) > 1023 or int(
                priority_value) < -1024:
            raise InvalidPriorityException
        ids = " ".join(scheduler_ids)
        args = ['bash', '--login', '-c',
                'job_ids=(%s); for job_id in "${job_ids[@]}";'
                ' do qalter -p %s $job_id ;done' % (ids, priority_value)]
        rc, out, err = exec_oscmd(
            args, timeout=self._config.timeout
        )
        if err:
            logger.error(
                "Update job priority failed, Error message is: %s",
                err.decode()
            )
        return out.decode(), err.decode()
