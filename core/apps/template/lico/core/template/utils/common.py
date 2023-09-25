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

import logging
import os
import pwd

from django.conf import settings

logger = logging.getLogger(__name__)


def convert_myfolder(fopr, user, origin_path):
    if not origin_path.startswith('MyFolder'):
        return origin_path
    return fopr.path_abspath(
        fopr.path_join(
            user.workspace,
            fopr.path_relpath(
                origin_path,
                start='MyFolder'
            )
        )
    )


def set_user_env(user, role="admin"):
    if role == 'admin':
        os.putenv('MODULEPATH', settings.TEMPLATE.MODULE_PATH)
    else:
        from lico.core.usermodule.utils import get_eb_module_file_path
        private_modulepath = get_eb_module_file_path(user.workspace)
        os.putenv(
            'MODULEPATH',
            f"{settings.TEMPLATE.MODULE_PATH}:{private_modulepath}"
        )

    os.chdir(user.workspace)
    os.setgid(user.gid)
    os.setuid(user.uid)
    os.putenv('LMOD_DIR', settings.TEMPLATE.LMOD_DIR)
    home_dir = pwd.getpwnam(user.username).pw_dir
    os.putenv('HOME', home_dir)
