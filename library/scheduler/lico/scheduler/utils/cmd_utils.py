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

from subprocess import PIPE, list2cmdline, run  # nosec B404


def exec_oscmd(args, timeout: int):
    process = run(
        args, stdout=PIPE, stderr=PIPE, timeout=timeout
    )
    return process.returncode, process.stdout, process.stderr


def exec_oscmd_with_login(args, timeout: int):
    process = run(  # nosec B603 B607
        [
            'bash', '--login', '-c',
            list2cmdline(args)
        ],
        stdout=PIPE,
        stderr=PIPE,
        timeout=timeout
    )
    return process.returncode, process.stdout, process.stderr


def exec_oscmd_with_user(user, args, timeout: int):
    process = run(  # nosec B603 B607
        [
            'su', '-', user, '-c',
            list2cmdline(args)
        ],
        stdout=PIPE,
        stderr=PIPE,
        timeout=timeout
    )
    return process.returncode, process.stdout, process.stderr
