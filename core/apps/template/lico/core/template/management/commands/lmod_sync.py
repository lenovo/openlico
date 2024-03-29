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

from django.conf import settings
from django.core.management.base import BaseCommand

from lico.ssh.ssh_connect import RemoteSSH

__all__ = ['Command']


class Command(BaseCommand):
    help = 'Sync hpc module to lico db.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--spider',
            default=os.path.join(settings.TEMPLATE.LMOD_DIR, 'spider'),
            help='The lmod spider tool path'
        )
        parser.add_argument(
            '--modulepath',
            default=settings.TEMPLATE.MODULE_PATH,
            help='Directories to search for modulefiles'
        )

    def handle(self, *args, **options):
        from os import path

        modulepath = options['modulepath']
        spider = options['spider']
        if modulepath is None:
            print('No modulepath available')
            return

        import json
        from subprocess import check_output  # nosec B404

        cmd = [spider, '-o', 'spider-json', modulepath]
        if not settings.JOB.JOB_SUBMIT_NODE_HOSTNAME:
            if not path.exists(spider):
                print('No spider tool available')
                return
            output = check_output(cmd)   # nosec B603
        else:
            output = self.exec_ssh_oscmd(settings.JOB.JOB_SUBMIT_NODE_HOSTNAME,
                                         settings.JOB.JOB_SUBMIT_NODE_PORT,
                                         cmd).stdout.strip()
        from lico.core.template.utils.lmod import sync
        sync(json.loads(output))

        from lico.core.template.models import Module
        for module in Module.objects.iterator():
            print(module.name)

    def exec_ssh_oscmd(self, hostname, port, cmd, timeout=30):
        with RemoteSSH(host=hostname, port=port) as conn:
            result = conn.run(cmd, command_timeout=timeout)
        return result
