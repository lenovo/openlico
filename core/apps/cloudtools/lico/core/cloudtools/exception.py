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

from rest_framework import status

from lico.core.contrib.exceptions import LicoError


class CloudToolException(LicoError):
    status_code = status.HTTP_400_BAD_REQUEST
    message = 'CloudTool operation error.'
    errid = 11000

    def __init__(self, msg=None):
        super(CloudToolException, self).__init__(msg)
        self.detail = {
            'msg': (msg or self.message),
            'errid': str(self.errid)
        }


class EnvironmentAlreadyUsed(CloudToolException):
    message = "The environment has already used"
    errid = 11001


class ProjectAlreadyExist(CloudToolException):
    message = 'Project has already exist'
    errid = 11002


class UnableDefaultProject(CloudToolException):
    message = 'Unable to operate the default project'
    errid = 11003


class ProjectBusyNow(CloudToolException):
    message = "The project is busy now"
    errid = 11004


class CloudToolSubmitException(CloudToolException):
    message = 'CloudTool submit failed'
    errid = 11005


class SettingAlreadyExist(CloudToolException):
    message = 'Setting has already exist'
    errid = 11006


class ProjectEnvDeleteException(CloudToolException):
    message = 'delete project env error, please try again'
    errid = 11007


class ProjectDoesNotExist(CloudToolException):
    message = "The project does not exist"
    errid = 11008


class ToolDoesNotExist(CloudToolException):
    message = "The tool does not exist"
    errid = 11009


class ToolSettingsDoesNotExist(CloudToolException):
    message = "The tool settings does not exist"
    errid = 11010


class ToolInstanceDoesNotExist(CloudToolException):
    message = "The tool instance does not exist"
    errid = 11011


class ToolBusyNow(CloudToolException):
    message = "The tool instance is already exist"
    errid = 11012


class PathFormatException(CloudToolException):
    message = "The path format is invalid"
    errid = 11013
