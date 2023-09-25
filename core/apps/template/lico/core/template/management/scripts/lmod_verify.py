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

import os
import sys
from os import path
from subprocess import PIPE, run  # nosec B404


def module(command, *args):
    _mlstatus = None
    lmod_exec = path.join(
            os.environ.get(
                'LMOD_DIR',
                '/opt/ohpc/admin/lmod/lmod/libexec'
            ), 'lmod'
        )
    args = [lmod_exec, 'python', command] + list(args)

    proc = run(args, stdout=PIPE, stderr=PIPE)  # nosec B603

    print(proc.stderr.decode(), file=sys.stderr)
    exec(proc.stdout.decode())  # nosec B102

    return not proc.returncode if _mlstatus is None else _mlstatus


def main():
    if not module('purge'):
        exit(1)

    mod_list = (mod.rstrip() for mod in sys.stdin if mod.rstrip())
    if mod_list and not module('load', *mod_list):
        exit(1)

    exit()
