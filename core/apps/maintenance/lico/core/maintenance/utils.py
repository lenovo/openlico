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

from subprocess import PIPE, run  # nosec B404

from lico.ssh import RemoteSSH


def get_hosts_from_job(job_obj):
    hosts = set()
    for running_job in job_obj.job_running:
        hosts_list = running_job.get('hosts', '').split(',')
        for host in hosts_list:
            if host != '':
                hosts.add(host)
    return hosts


def get_resource_from_job(job_obj):
    """
    lsf: C:4,G/gpu/4/1:1
    slurm: M:778.54,N:1,C:4.0,G/gpu/3g.20gb:1.0
    pbs: C:4.0,G/gpu:1.0,N:1.0,M:4380.54
    """
    host_resource = dict()
    for running_job in job_obj.job_running:
        hosts = running_job.get("hosts").split(',')
        per_host_resource = running_job.get('per_host_tres').split(',')
        resource = {
            'cpu': 0,
            'mem': 0  # units: KB
        }
        for resource_type in per_host_resource:
            key, value = resource_type.split(':')
            if key == 'C':
                resource['cpu'] += float(value)
            elif key == 'M':
                resource['mem'] += float(value) * 1024
                # units MB -> KB
            elif key.startswith('G/'):
                new_key = key[2:].split("/")[0]
                if new_key in resource:
                    resource[new_key] += float(value)
                else:
                    resource[new_key] = float(value)

        host_resource.update({host: resource for host in hosts})

    return host_resource


def get_hosts_from_running_job(attr, running_jobs, filter_value):
    hostname_set = set()
    for job in running_jobs:
        if getattr(job, attr) == filter_value:
            hostname_set = hostname_set | get_hosts_from_job(job)
    return list(hostname_set)


def sum_resource(resource_used_dict, resource):
    for key, value in resource.items():
        if key in resource_used_dict:
            resource_used_dict[key] += value
        else:
            resource_used_dict[key] = value


def exec_oscmd(cmd, args=None, timeout=30):
    process = run(  # nosec B603
        cmd, input=args, stdout=PIPE, stderr=PIPE, timeout=timeout
    )
    return process.returncode, process.stdout, process.stderr


def exec_ssh_oscmd(hostname, cmd, args=None, timeout=30):
    with RemoteSSH(host=hostname) as conn:
        process = conn.run(
            cmd, in_stream=args, out_stream=PIPE, err_stream=PIPE,
            command_timeout=timeout
        )
    return process.exited, process.stdout, process.stderr
