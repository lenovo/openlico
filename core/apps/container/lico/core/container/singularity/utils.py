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

import itertools
import os
import pwd
import re
import stat
from enum import Enum
from subprocess import CalledProcessError, check_call, check_output

from django.conf import settings
from py.path import local

from lico.core.container.exceptions import (
    ContainSetUpError, FileAccessDenied, FileFormatIncorrect,
    ImageFileNotExist, SingularityNotExists, UnrecognizedImageType,
)


def user_image_path(workspace):
    return local(workspace).join('.lico')\
        .join('container').ensure(dir=True)


def get_singularity_path():
    try:
        out_put = check_output([
            'bash',
            '--login',
            '-c',
            'which singularity']
        ).strip().decode()
    except CalledProcessError as e:
        raise SingularityNotExists from e

    return ignore_no_singularity(out_put)


def check_original_path(file_path):

    if not file_path.isfile():
        raise ImageFileNotExist
    if "SINGULARITY_PATH" in settings.CONTAINER:
        singularity_path = settings.CONTAINER.SINGULARITY_PATH
    else:
        singularity_path = get_singularity_path()
    if "singularity" not in singularity_path:
        raise SingularityNotExists
    try:
        check_call(
            [singularity_path, 'inspect', file_path]
        )
    except CalledProcessError as e:
        raise UnrecognizedImageType from e


def change_owner(image, target_path):
    username = image.username
    if username != '':
        user = pwd.getpwnam(username)
        target_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    else:
        user = pwd.getpwnam("root")
        target_path.chmod(
            stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH
        )
    target_path.chown(user.pw_uid, user.pw_gid)


class TaskStatus(Enum):
    PENDING = 0  # The task is waiting for execution.
    STARTED = 1  # The task has been started by a worker.
    SUCCESS = 2  # The task executed successfully.
    FAILURE = 3  # The task raised an exception.


def check_definition_validity(file_path, workspace):
    try:
        data_list = local(file_path).readlines()
    except Exception as e:
        raise FileFormatIncorrect from e

    setup_list = list(itertools.filterfalse(
        lambda item: re.match(r'^%setup(\s+.*)?\s*$', item) is None, data_list)
    )
    if setup_list:
        raise ContainSetUpError

    list1 = list(itertools.dropwhile(
        lambda item: re.match(r'^%files(\s+.*)?\s*$', item) is None,
        data_list))[1:]
    files_list = list(itertools.takewhile(
        lambda item: re.match(r'^%(\S+)(\s+.*)?\s*$', item) is None, list1)
    )
    for i in files_list:
        if i.strip().startswith('/') and \
                local(workspace) not in local(i.strip()).parts():
            raise FileAccessDenied


def ignore_no_singularity(out_put):
    output_lines = out_put.splitlines()
    singularity_commands = list(
        itertools.filterfalse(
            lambda item: True if re.search(
                r'singularity$', item) is None
            else not os.path.exists(item),
            output_lines
        )
    )
    if not singularity_commands:
        raise SingularityNotExists
    return singularity_commands[0]
