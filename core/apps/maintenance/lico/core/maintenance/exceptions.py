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

from rest_framework import status

from lico.core.contrib.exceptions import LicoError


class MaintenanceException(LicoError):
    status_code = status.HTTP_400_BAD_REQUEST
    message = ' Maintenance operation error.'
    errid = 22000

    def __init__(self, msg=None):
        super(MaintenanceException, self).__init__(msg)
        self.detail = {
            'msg': (msg or self.message),
            'errid': str(self.errid)
        }


class TerminateProcessException(MaintenanceException):
    message = "Terminate Process error."
    errid = 22001


class TerminateFileConfigException(MaintenanceException):
    message = "Please config kill_file_path in maintenance.ini."
    errid = 22002


class TerminateNoPermissionException(MaintenanceException):
    message = "No permission error."
    errid = 22003
