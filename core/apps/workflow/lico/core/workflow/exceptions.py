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


class WorkflowModuleException(LicoError):
    message = 'Workflow module api error.'
    errid = 15000


class CreateWorkflowException(WorkflowModuleException):
    message = 'Create Workflow failed.'
    errid = 15001


class WorkflowStepAlreadyExist(WorkflowModuleException):
    message = "This WorkflowStep already exists"
    errid = 15002


class CreateWorkflowStepException(WorkflowModuleException):
    message = 'Create WorkflowStep failed.'
    errid = 15003


class CreateWorkflowStepJobException(WorkflowModuleException):
    message = 'Create WorkflowStepJob failed.'
    errid = 15004


class WorkflowOperationException(WorkflowModuleException):
    message = "Workflow's current status does not support specified operation."
    errid = 15005


class WorkflowSummaryInfoMissingException(WorkflowModuleException):
    message = "The Workflow is missing summary information."
    errid = 15006
