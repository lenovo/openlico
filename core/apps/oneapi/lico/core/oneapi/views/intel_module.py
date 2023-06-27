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

import glob
import os

from django.conf import settings
from rest_framework.response import Response

# from rest_framework.views import APIView
from lico.core.contrib.views import APIView

INTEL_MODULEFILES_LIST = ['/**/**/modulefiles/**']


class IntelModuleListView(APIView):
    def get(self, request):
        intel_module_path = settings.ONEAPI.INTEL_MODULE_PATH
        modulefiles_list = INTEL_MODULEFILES_LIST
        modlist = []
        if intel_module_path:
            for modulefile in modulefiles_list:
                module_files_names = glob.glob(
                    intel_module_path + modulefile)

                modlist.extend(list(set(os.path.basename(name)
                               for name in module_files_names)))

        return Response(modlist)
