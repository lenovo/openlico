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

import os
import shutil
import sys

from django.conf import settings
from django.core.management.base import BaseCommand

from . import print_red


class Command(BaseCommand):
    help = 'init user share dirs'

    def add_arguments(self, parser):
        parser.add_argument(
            '--skeleton',
            default='/etc/skel',
            help='The skeleton directory path'
        )

        parser.add_argument(
            '--share_dir_prefix',
            default='lico_share_dir',
            help='User-defined shared directory name'
        )

    def handle(self, *args, **options):
        if settings.LICO.ARCH != 'host':
            return

        share_dirs = settings.LICO.USER_SHARE_DIR
        skeleton_dir = options['skeleton']
        share_dir_name = options['share_dir_prefix']

        share_dir_root = os.path.join(
            skeleton_dir, share_dir_name
        )

        if os.path.exists(share_dir_root):
            shutil.rmtree(share_dir_root)

        os.mkdir(share_dir_root)

        if share_dirs:
            for des in share_dirs:
                src = os.path.abspath(des)
                dest = os.path.abspath(
                    os.path.join(
                        share_dir_root,
                        os.path.basename(des)
                    )
                )

                if not os.path.islink(dest):
                    try:
                        os.symlink(src, dest)
                    except OSError as e:
                        print_red(
                            'OSError: {} Dest: {}'.format(e, dest)
                        )
                        sys.exit(1)
