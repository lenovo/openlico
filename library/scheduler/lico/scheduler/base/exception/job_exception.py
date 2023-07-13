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


class SchedulerJobBaseException(Exception):
    message = 'Scheduler job error.'


class TokenInvalidException(SchedulerJobBaseException):
    message = 'Invalid Service Token.'


class ServerInvalidException(SchedulerJobBaseException):
    message = 'Server is Invalid.'


class JobFileNotExistException(SchedulerJobBaseException):
    message = 'Job file does not exist.'


class SubmitJobFailedException(SchedulerJobBaseException):
    message = 'Submit job failed.'


class CancelJobFailedException(SchedulerJobBaseException):
    message = 'Cancel job failed.'


class HoldJobFailedException(SchedulerJobBaseException):
    message = 'Hold job failed.'


class ReleaseJobFailedException(SchedulerJobBaseException):
    message = 'Release job failed.'


class RecycleResourceFailedException(SchedulerJobBaseException):
    message = 'Recycle resource failed.'


class InvalidTimeFormatException(SchedulerJobBaseException):
    message = 'Invalid time format.'


class InvalidJobIdentityStringException(SchedulerJobBaseException):
    message = 'Invalid job identity string.'


class QueryJobFailedException(SchedulerJobBaseException):
    message = 'Query job failed.'


class QueryJobRawInfoFailedException(SchedulerJobBaseException):
    message = 'Query job raw info failed.'


class NodeListParseException(SchedulerJobBaseException):
    message = 'Parse node list failed.'


class SchedulerNotWorkingException(SchedulerJobBaseException):
    message = 'Scheduler is not working.'


class AcctNoFileException(SchedulerJobBaseException):
    message = "Acct File is Not Exist."


class AcctInvalidValueException(SchedulerJobBaseException):
    message = "The field value is invalid."


class AcctInvalidVersionException(SchedulerJobBaseException):
    message = "Invalid LSF version."


class AcctNoFieldException(SchedulerJobBaseException):
    message = "Can not find the field."


class UnknownSubmitTimeException(SchedulerJobBaseException):
    message = "Get submit time str 'Unknown'."


class AcctException(SchedulerJobBaseException):
    message = "Slurm acct parser failed."


class SchedulerConnectTimeoutException(SchedulerJobBaseException):
    message = "Scheduler connect timeout."


class ServerDownException(SchedulerJobBaseException):
    message = "Scheduler server is down."


class QueryRuntimeException(SchedulerJobBaseException):
    message = "Query runtime failed."


class QueryUserPriorityException(SchedulerJobBaseException):
    message = "Query user priority failed."


class InvalidPriorityException(SchedulerJobBaseException):
    message = "Invalid Priority."


class SetPriorityException(SchedulerJobBaseException):
    message = "Failed to set the job priority."


class RequeueJobException(SchedulerJobBaseException):
    message = "Failed to requeue the job."
