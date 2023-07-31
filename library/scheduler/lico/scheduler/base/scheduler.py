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

from abc import ABCMeta, abstractmethod
from typing import List

from .job.job import Job
from .job.job_identity import IJobIdentity
from .job.queue import Queue


class IScheduler(metaclass=ABCMeta):

    @abstractmethod
    def submit_job(
            self,
            job_content: str,
            job_comment: str = None,
            job_name: str = None
    ) -> IJobIdentity:
        pass

    @abstractmethod
    def submit_job_from_file(
            self,
            job_filename: str,
            job_comment: str = None,
            job_name: str = None
    ) -> IJobIdentity:
        pass

    @abstractmethod
    def cancel_job(self, scheduler_ids: list) -> None:
        pass

    @abstractmethod
    def job_action(
            self,
            scheduler_ids: list,
            command: List[str],
            action: str
    ):
        pass

    @abstractmethod
    def hold_job(self, scheduler_ids: list) -> None:
        pass

    @abstractmethod
    def release_job(self, scheduler_ids: list) -> None:
        pass

    @abstractmethod
    def query_job(self, job_identity: IJobIdentity) -> Job:
        pass

    @abstractmethod
    def query_job_raw_info(self, job_identity: IJobIdentity) -> str:
        pass

    @abstractmethod
    def query_recent_jobs(self, query_memory: bool = True) -> List[Job]:
        pass

    @abstractmethod
    def query_available_queues(self) -> List[Queue]:
        pass

    @abstractmethod
    def get_status(self) -> bool:
        pass

    @abstractmethod
    def get_runtime(self) -> int:
        pass

    @abstractmethod
    def recycle_resources(self, job_identity: IJobIdentity):
        pass

    @abstractmethod
    def get_history_job(
            self,
            starttime_stamp: int,
            endtime_stamp: int
    ) -> List[Job]:
        pass

    @abstractmethod
    def get_scheduler_config(self, *args) -> dict:
        pass

    @abstractmethod
    def get_license_feature(self) -> list:
        pass

    @abstractmethod
    def get_priority_value(self) -> dict:
        pass

    @abstractmethod
    def update_job_priority(self, scheduler_ids: list,
                            priority_value: str) -> str:
        pass

    @abstractmethod
    def requeue_job(self, scheduler_ids: list) -> str:
        pass

    def batch_command_status(self, scheduler_nums: int, err_nums: int) -> str:
        if err_nums == 0:
            return "success"
        elif err_nums < scheduler_nums:
            return "partial"
        else:
            return "fail"
