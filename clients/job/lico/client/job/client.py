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
from typing import List

import attr

from lico.client.contrib.client import BaseClient

logger = logging.getLogger(__name__)


class Client(BaseClient):
    app = 'job'

    def handle_exception(self, exc, response):  # pragma: no cover
        logger.exception('Unknown exception')
        try:
            response.json()
        except Exception:
            pass
        else:
            # while job rasie 400 exception, can also get job id
            return

        super().handle_exception(exc, response)

    def query_job(self, job_id):
        if self.username is None:
            url = f'internal/{job_id}/'
        else:
            url = f'{job_id}/'
        response = self.get(
            self.get_url(url),
        )
        return response

    def cancel_job(self, job_id):
        response = self.put(
            self.get_url(f'{job_id}/'),
        )
        return response

    def submit_job(self, job_name, workspace, job_content):
        req_data = {
            'job_name': job_name,
            'workspace': workspace,
            'job_content': job_content
        }
        response = self.post(
            self.get_url('submit/'),
            json=req_data
        )
        return response

    def submit_job_file(self, job_name, job_file):
        req_data = {
            'job_name': job_name,
            'job_file': job_file
        }
        response = self.post(
            self.get_url('submit/'),
            json=req_data
        )
        return response

    def rerun_job(self, job_id):
        response = self.post(
            self.get_url(f'rerun/{job_id}/')
        )
        return response

    def query_available_queues(self):
        response = self.get(
            self.get_url('queue/')
        )
        return response

    def get_running_job_resource(self):
        @attr.s(frozen=True)
        class RunningJobResource:
            core_total_num: int = attr.ib()
            gpu_total_num: float = attr.ib()

        response = self.get(
            self.get_url('running_job/resource/')
        )
        return RunningJobResource(
            core_total_num=response["core_total_num"],
            gpu_total_num=response["gpu_total_num"]
        )

    def get_host_resource_used(self):
        """
        :return: {
        'c1':{'runningjob_num':0, 'core_total_num':10, 'gpu_total_num':2},
        'c2':{'runningjob_num':2, 'core_total_num':10, 'gpu_total_num':2},..
        }
        """
        response = self.get(
            self.get_url('host_resource_used/'),
        )
        return response

    def query_recent_jobs(self, end_time_offset=300):
        url = 'recent_job/user_job/' if self.username else 'recent_job/'
        response = self.get(
            self.get_url(url),
            params={'end_time_offset': end_time_offset}

        )
        return response

    def sync_history_job(
            self,
            start_time: int,
            end_time: int,
            exclude_ids: List[str]
    ) -> List:
        req_data = {
            "start_time": start_time,
            "end_time": end_time,
            "exclude_ids": exclude_ids
        }
        response = self.post(
            self.get_url('sync/history_job/'),
            json=req_data,
        )

        return response

    def query_running_jobs(self, verbose=0):
        from .dataclass import DetailedJob, Job
        url = 'running/jobs/'
        jobs_dict = self.get(
            self.get_url(url),
            params={'verbose': verbose}
        )
        if verbose == 1:
            _Job = DetailedJob
        else:
            _Job = Job
        response = []
        for job_dict in jobs_dict:
            job = _Job(**job_dict)
            response.append(job)
        return response

    def job_list(self, job_id_list, submitter):
        req_data = {
            "job_id_list": job_id_list,
            "submitter": submitter
        }
        response = self.post(
            self.get_url('job_list/'),
            json=req_data
        )
        return response
