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

from lico.core.contrib.exceptions import LicoError


class JobException(LicoError):
    message = 'Job module api error.'
    errid = 7000


class JobFileNotExist(JobException):
    message = 'Job file not exist.'
    errid = 2001

    def __str__(self):
        return self.message


class DeleteRunningJobException(JobException):
    message = 'Delete running job is not allowed.'
    errid = 7003


class SubmitJobException(JobException):
    message = 'Submit job failed.'
    errid = 7004

    def __init__(self, job_id):
        super(LicoError, self).__init__()
        self.detail = {
            'msg': self.message,
            'id': int(job_id) if job_id else None,
            'errid': str(self.errid)
        }


class SyncHistoryJobException(JobException):
    message = 'Sync history job failed.'
    errid = 7005


class InvalidParameterException(JobException):
    errid = 7006
    message = 'Invalid parameter.'


class QueryJobDetailException(JobException):
    errid = 7007
    message = "Query job detail failed."


class QuerySchedulerRuntimeException(JobException):
    errid = 7008
    message = "Query scheduler runtime failed."


class QuerySchedulerLicenseFeatureException(JobException):
    errid = 7009
    message = "Query scheduler license feature failed."
