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


class InvalidJobPriorityException(JobException):
    errid = 7010
    message = "Invalid job priority."


class QueryJobPriorityException(JobException):
    errid = 7011
    message = "Query job priority failed."


class AdjustJobPriorityException(JobException):
    errid = 7012
    message = "Failed to set the job priority."


class HoldJobException(JobException):
    errid = 7013
    message = "Failed to hold the job"


class ReleaseJobException(JobException):
    errid = 7014
    message = "Failed to release the job"


class RequeueJobException(JobException):
    errid = 7015
    message = "Failed to requeue the job."


class InvalidUserRoleException(JobException):
    errid = 7016
    message = "Submit an Invalid user role."


class InvalidJobIDException(JobException):
    errid = 7017
    message = "Submit Invalid job id."


class JobOperationNotSupportException(JobException):
    errid = 7018
    message = "Requeue job operation is not supported."


class JobOperationException(JobException):
    errid = 7019
    message = "Job operation exception."


class SuspendJobException(JobException):
    errid = 7020
    message = "Failed to suspend the job"


class ResumeJobException(JobException):
    errid = 7021
    message = "Failed to resume the job"
