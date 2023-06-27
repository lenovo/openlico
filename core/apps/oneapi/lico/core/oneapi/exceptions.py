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


class OneApiException(LicoError):
    message = 'oneAPI module api error'
    errid = 23000

    def __str__(self):
        return self.message


class VtuneTimeOutException(OneApiException):
    message = 'start job timeout'
    errid = 23001

    def __str__(self):
        return self.message


class VtuneFailedException(OneApiException):
    message = 'Failed to start Intel VTune Profiler'
    errid = 23002

    def __str__(self):
        return self.message


class NotAFileException(OneApiException):
    message = 'Invalid file format of Intel VTune Profiler result'
    errid = 23006

    def __str__(self):
        return self.message


class PathNotExistException(OneApiException):
    message = 'Can not find Intel VTune Profiler result file'
    errid = 23007

    def __str__(self):
        return self.message


class PermissionDeniedException(OneApiException):
    message = 'No permission to access Intel VTune Profiler result'
    errid = 23008

    def __str__(self):
        return self.message


class ReportDownloadException(OneApiException):
    message = 'Failed to download Intel VTune Profiler report'
    errid = 23009

    def __str__(self):
        return self.message
