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

from rest_framework.status import HTTP_400_BAD_REQUEST

from lico.core.contrib.exceptions import LicoError


class UserModuleException(LicoError):
    status_code = HTTP_400_BAD_REQUEST
    message = 'User module api error.'
    errid = 16000


class EasyconfigNotFoundException(UserModuleException):
    errid = 16001
    message = 'Easyconfig not found.'


class UserModuleDeleteFailed(UserModuleException):
    errid = 16002
    message = 'User module delete failed.'


# =============== HTTP_500 ===============
class UserModuleSubmitException(Exception):
    message = 'Usermodule submit job failed.'


class UserModuleGetPrivateModuleException(Exception):
    message = 'Failed to get private module.'


class ModulepathNotExistedException(Exception):
    message = 'Modulepath is not existed.'


class SpiderToolNotAvailableException(Exception):
    message = 'Spider tool is not available.'


class UserModulePermissionDenied(Exception):
    message = 'The current user has no permission to perform operations.'


class UserModuleFailToGetJobException(Exception):
    message = 'Failed to get job.'
