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

import logging
from datetime import datetime

from django.conf import settings
from py.path import local
from rest_framework.response import Response

from lico.core.contrib.permissions import AsAdminRole
from lico.core.contrib.views import APIView

logger = logging.getLogger(__name__)


class ScriptView(APIView):
    permission_classes = (AsAdminRole, )

    def get(self, request):
        scripts_info = [
            {
                'name': filename.basename,
                'size': filename.size(),
                'modify_time': datetime.utcfromtimestamp(
                    filename.mtime()
                ).strftime('%Y-%m-%dT%H:%M:%SZ')
            }
            for filename in local(settings.ALERT.SCRIPTS_DIR).listdir()
            if not filename.isdir() and not filename.basename.startswith('.')
        ]
        return Response(scripts_info)
