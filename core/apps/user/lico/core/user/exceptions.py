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

from typing import Optional

from rest_framework.status import (
    HTTP_401_UNAUTHORIZED, HTTP_500_INTERNAL_SERVER_ERROR,
)

from lico.core.contrib.exceptions import LicoError

from .models import User


class UserModuleException(LicoError):
    message = 'User module api error.'
    errid = 2000


class SecretFileDoesNotExist(UserModuleException):
    status_code = HTTP_500_INTERNAL_SERVER_ERROR


class LoginFail(UserModuleException):
    status_code = HTTP_401_UNAUTHORIZED
    message = "Invalid username/password."
    errid = 2013

    def __init__(self, user: Optional[User] = None):
        super().__init__()
        if user:
            self.detail['detail'] = {
                'fail_chances': user.fail_chances,
                'remain_chances': user.remain_chances,
                'remain_time': user.remain_time.total_seconds()
            }


class ModifyPasswordFailed(UserModuleException):
    message = 'Fail to modify password.'
    errid = 2104


class LibuserConfigException(UserModuleException):
    errid = 2105
    message = 'Invalid libuser config'


class InvalidUser(UserModuleException):
    errid = 2106
    message = 'Invalid user.'


class InvalidGroup(UserModuleException):
    errid = 2107
    message = 'Invalid group.'


class InvalidOperation(UserModuleException):
    errid = 2108
    message = 'Invalid operation.'


class GroupAlreadyExist(UserModuleException):
    message = "Group already exists"
    errid = 2110


class InvalidLibuserOperation(UserModuleException):
    message = "Invalid libuser operation"
    errid = 2111


class UserAlreadyExist(UserModuleException):
    message = "User already exists"
    errid = 2112


class RemoveLastAdmin(UserModuleException):
    message = 'Unable to remove last administrator.'
    errid = 2115


class UserNotExists(UserModuleException):
    errid = 2116
    message = 'User not exists in ldap'


class GroupNotExists(UserModuleException):
    message = "Group not exists"
    errid = 2117


class TitleFieldsInvalid(UserModuleException):
    message = 'Title fields invalid.'
    errid = 2201


class UserDuplicate(UserModuleException):
    message = 'User already exists.'
    errid = 2202


class UserRoleInvalid(UserModuleException):
    message = 'The role does not exist.'
    errid = 2204


class FileFormatInvalid(UserModuleException):
    message = 'The format of file is invalid.'
    errid = 2205


class UserEmpty(UserModuleException):
    message = 'Username cannot be empty.'
    errid = 2208


class CannotCancelImportRecordProcess(UserModuleException):
    message = 'Can not cancel the Import Record Process.'
    errid = 2212


class RunningWorkExists(UserModuleException):
    message = 'Running worker exists.'
    errid = 2213
