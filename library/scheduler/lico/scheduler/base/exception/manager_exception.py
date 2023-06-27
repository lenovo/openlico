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


class SchedulerManagerBaseException(Exception):
    message = 'Scheduler manager error.'


class DeserializeQueueSettingException(SchedulerManagerBaseException):
    message = 'Deserialize dict to queue setting failed.'


class DeserializeOverSubscribeException(SchedulerManagerBaseException):
    message = 'Deserialize string to over_subscribe failed.'


class QueryNodeStateException(SchedulerManagerBaseException):
    message = 'Query queue node state failed.'


class UnknownActionException(SchedulerManagerBaseException):
    message = 'Unknown action for updating queue nodes state.'


class UpdateNodeStateException(SchedulerManagerBaseException):
    message = 'Update queue nodes state failed.'


class QuerySlurmctlServiceStatusException(SchedulerManagerBaseException):
    message = 'Query slurmctld service status failed.'


class SaveSlurmConfigurationFileException(SchedulerManagerBaseException):
    message = 'Save slurm conf file failed.'


class QueryQueueException(SchedulerManagerBaseException):
    message = 'Query queue failed.'


class QueueNotExistException(SchedulerManagerBaseException):
    message = 'Queue not exist.'


class QueueBusyException(SchedulerManagerBaseException):
    message = 'Queue is busy now.'


class DeleteQueueException(SchedulerManagerBaseException):
    message = 'Delete queue failed.'


class UpdateQueueStateException(SchedulerManagerBaseException):
    message = 'Update queue state failed.'


class QueueAlreadyExistException(SchedulerManagerBaseException):
    message = 'Queue already exists.'


class NodeNotExistException(SchedulerManagerBaseException):
    message = 'Scheduler nodes not exist.'


class QueryQueueDetailException(SchedulerManagerBaseException):
    message = 'Query queue detail failed.'


class CreateQueueException(SchedulerManagerBaseException):
    message = 'Create queue failed.'


class UpdateQueueException(SchedulerManagerBaseException):
    message = 'Update queue failed.'


class GPUConfigurationException(SchedulerManagerBaseException):
    message = 'GPU configuration error.'


class QueryLicenseFeatureException(SchedulerManagerBaseException):
    message = 'Query license feature error.'


class QueryLimitationException(SchedulerManagerBaseException):
    message = 'Query limitation failed.'


class LimitationAlreadyExistException(SchedulerManagerBaseException):
    message = 'Limitation already exists.'


class CreateLimitationException(SchedulerManagerBaseException):
    message = 'Create limitation failed.'


class QueryLimitationDetailException(SchedulerManagerBaseException):
    message = 'Query limitation detail failed.'


class LimitationNotExistException(SchedulerManagerBaseException):
    message = 'Limitation does not exist.'


class DeleteLimitationException(SchedulerManagerBaseException):
    message = 'Delete Limitation failed.'


class LimitationInUseException(SchedulerManagerBaseException):
    message = 'Limitation still in use'


class UpdateLimitationException(SchedulerManagerBaseException):
    message = 'Update limitation failed.'


class QueryAccountException(SchedulerManagerBaseException):
    message = 'Query account failed.'


class CreateAccountException(SchedulerManagerBaseException):
    message = 'Create account failed.'


class CreateAssociationException(SchedulerManagerBaseException):
    message = 'Create association failed.'


class AccountNotExistException(SchedulerManagerBaseException):
    message = 'Account does not exist.'


class DeleteAssociationException(SchedulerManagerBaseException):
    message = 'Delete association failed.'


class PerJobMaxRuntimeWrongFormat(SchedulerManagerBaseException):
    message = 'Per Job Max Runtime is in wrong format'


class GresNotAvailableException(SchedulerManagerBaseException):
    message = 'Current Gres is not available in slurm. Define it in slurm.conf\
        first.'
