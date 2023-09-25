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


class LicoError(APIException):
    status_code = HTTP_400_BAD_REQUEST
    message = 'lico core api error'
    errid = 1000

    def __init__(self, msg=None):
        super().__init__(msg)
        self.detail = {
            'msg': (msg or self.message),
            'errid': str(self.errid)
        }


class LicoInternalError(APIException):
    status_code = HTTP_500_INTERNAL_SERVER_ERROR
    message = 'lico internal server error'

    def __init__(self, msg=None):
        super().__init__(msg)
        self.detail = {
            'msg': (msg or self.message),
        }


class InvalidJSON(LicoError):
    errid = 1002
    message = 'Invalid JSON Format'

    def __init__(self, e):
        super().__init__()
        self.detail['detail'] = str(e)
