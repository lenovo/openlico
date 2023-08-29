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

from typing import List

import attr


@attr.s
class Job:
    id = attr.ib(type=int)
    submitter = attr.ib(type=str)
    scheduler_id = attr.ib(type=str)
    job_name = attr.ib(type=str)
    workspace = attr.ib(type=str)
    tres = attr.ib(type=str)
    queue = attr.ib(type=str)
    submit_time = attr.ib(type=int)
    job_running: List[dict] = attr.ib(kw_only=True)

    @property
    def hosts(self):
        hosts = set()
        for running_job in self.job_running:
            hosts_list = running_job.get('hosts', '').split(',')
            for host in hosts_list:
                if host != '':
                    hosts.add(host)
        return hosts

    @property
    def resource(self):
        resource = {'cpu': 0, 'mem': 0}
        for running_job in self.job_running:
            per_host_resource = running_job.get('per_host_tres').split(',')
            for resource_type in per_host_resource:
                key, value = resource_type.split(':')
                if key == 'C':
                    resource['cpu'] += float(value)
                elif key == 'M':
                    # units MB
                    resource['mem'] += float(value)
                elif key.startswith('G/'):
                    new_key = key[2:]
                    if new_key in resource:
                        resource[new_key] += float(value)
                    else:
                        resource[new_key] = float(value)
        resource['mem'] = resource['mem'] * 1024
        # units to KB
        return resource


@attr.s
class DetailedJob(Job):
    identity_str = attr.ib(type=str)
    start_time = attr.ib(type=int)
    end_time = attr.ib(type=int)
    scheduler_state = attr.ib(type=str)
    state = attr.ib(type=str)
    runtime = attr.ib(type=int)
    create_time = attr.ib(type=int)
    update_time = attr.ib(type=int)
