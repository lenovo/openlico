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

from rest_framework.exceptions import APIException
from rest_framework.status import (
    HTTP_400_BAD_REQUEST, HTTP_500_INTERNAL_SERVER_ERROR,
)


class MonitorException(APIException):
    status_code = HTTP_400_BAD_REQUEST
    message = 'Cluster operation error'
    errid = 3000

    def __init__(self, msg=None):
        super(MonitorException, self).__init__(msg)
        self.detail = {
            'msg': (msg or self.message),
            'errid': str(self.errid)
        }

    def __str__(self):  # pragma: no cover
        return '{}: error_id {}, "{}"'.format(
            self.__class__.__name__,
            self.detail.get('errid', None),
            self.detail.get('msg', None),
        )


class CheckPreferenceException(MonitorException):
    status_code = HTTP_500_INTERNAL_SERVER_ERROR
    errid = 3002
    message = 'Check preference policy failed.'


class SSHConnectException(MonitorException):
    errid = 3003
    message = 'SSH Connect failed.'


class InfluxDBException(MonitorException):
    status_code = HTTP_400_BAD_REQUEST
    errid = 3008
    message = 'InfluxDB status failed.'


class InvalidParamException(MonitorException):
    status_code = HTTP_400_BAD_REQUEST
    errid = 3009
    message = 'Invalid param'


class ExportReportException(MonitorException):
    status_code = HTTP_400_BAD_REQUEST
    errid = 3010
    message = 'Export report failed !'


class HostNameDoesNotExistException(MonitorException):
    status_code = HTTP_400_BAD_REQUEST
    errid = 3011
    message = 'Get hostname failed!'


class UsernamePasswordNotSet(Exception):
    def __int__(self, serivce):
        self.err = f"{serivce} username or password not set"
        super().__init__(self, self.err)


class InvalidDeviceIdException(MonitorException):
    status_code = HTTP_400_BAD_REQUEST
    errid = 3012
    message = 'Invalid device id!'
