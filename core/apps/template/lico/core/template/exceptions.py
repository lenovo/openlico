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


class TemplateException(LicoError):
    message = 'template operation error.'
    errid = 4000


class JobCommandException(TemplateException):
    message = 'submit_job command error.'
    errid = 4001


class RuntimeAlreadyExist(TemplateException):
    message = 'Runtime has already exist.'
    errid = 4002


class ModuleInvalid(TemplateException):
    message = 'Modules Invalid.'
    errid = 4003

    def __init__(self, output):
        super(LicoError, self).__init__()
        self.detail = {
            'msg': self.message,
            'output': output,
            'errid': str(self.errid)
        }


class JobWorkdirNotExist(TemplateException):
    message = 'Job workdir not exists.'
    errid = 4004


class TemplateNotExist(TemplateException):
    message = 'Template not exists'
    errid = 4005


class RuntimeNotExist(TemplateException):
    message = 'Runtime not exists.'
    errid = 4006


class JobFileNotExist(TemplateException):
    message = 'Job file not exist.'
    errid = 4007


class UserTemplateExistsException(TemplateException):
    message = 'User template name already exists.'
    errid = 4008


class InvalidLogoException(TemplateException):
    message = 'Invalid logo type.'
    errid = 4009


class LogoSizeTooLargeException(TemplateException):
    message = 'Logo Size Too Large.'
    errid = 4010


class TemplateRenderException(TemplateException):
    message = 'The job template rendering error.'
    errid = 4024


class TemplateRenderPathException(TemplateException):
    message = "The path can't have blank character."
    errid = 4025


class ImportSchedulerException(TemplateException):
    message = "The scheduler type is not supported"
    errid = 4028


class ImportChecksumException(TemplateException):
    message = "Check template file failed"
    errid = 4029


class ImportVersionException(TemplateException):
    message = "The version of this template file is not supported"
    errid = 4030


class FavoTemplateExistsException(TemplateException):
    message = "Favorite template already exists."
    errid = 4031


class FavoTemplateNotExistException(TemplateException):
    message = "Favorite template not exists."
    errid = 4032


class JupyterImageNotExist(TemplateException):
    message = 'Jupyter image not exist.'
    errid = 4034


class SubmitJobException(TemplateException):
    message = 'Submit job failed.'
    errid = 4036


class ScriptFileDuplicateException(TemplateException):
    message = 'Script file is not allowed to be repeated'
    errid = 4037


class RstudioImageNotExist(TemplateException):
    message = 'RStudio image not exist.'
    errid = 4038


class UnknownSchedulerException(TemplateException):
    message = 'Unknown Scheduler Exception'
    errid = 4040


class IntelTensorFlowImageNotExist(TemplateException):
    message = 'Intel TensorFlow image not exist.'
    errid = 4041


class JupyterLabImageNotExist(TemplateException):
    message = 'JupyterLab image not exist.'
    errid = 4042
