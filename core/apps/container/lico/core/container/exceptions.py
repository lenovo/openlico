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


class ContainerException(LicoError):
    message = 'Container operation error.'
    errid = 9000


class ImageAlreadyExist(ContainerException):
    message = 'Image has already exist'
    errid = 9001


class UnrecognizedImageType(ContainerException):
    message = 'Unrecognized Image Type.'
    errid = 9002


class ImageFileNotExist(ContainerException):
    message = 'Image file is not exist.'
    errid = 9003


class ImageNotReady(ContainerException):
    message = 'Image is not ready.'
    errid = 9004


class TargetFileAlreadyExist(ContainerException):
    message = 'Target file is already exist '
    errid = 9005


class SingularityNotExists(ContainerException):
    errid = 9006
    message = 'Can not find singularity program.'


class MaxJobsReached(ContainerException):
    errid = 9007
    message = 'Max Jobs Reached.'


class BuildImageFailed(ContainerException):
    errid = 9009
    message = 'Failed to start image build.'


class UnknowError(Exception):
    pass


class FileAccessDenied(ContainerException):
    errid = 9010
    message = 'Invalid singularity definition file:' \
              ' In %files section, file access denied,' \
              ' please check and try again.'


class ContainSetUpError(ContainerException):
    errid = 9011
    message = 'Invalid singularity definition file:' \
              ' must not contain %setup section. ' \
              'please remove and try again.'


class AnotherJobRunning(ContainerException):
    errid = 9012
    message = 'Another job is running'


class FileFormatIncorrect(ContainerException):
    errid = 9013
    message = 'Incorrect file format'


class WorkSpaceNotExists(ContainerException):
    errid = 9014
    message = 'WorkSpace not exists'
