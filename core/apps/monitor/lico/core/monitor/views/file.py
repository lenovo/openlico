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

from rest_framework.response import Response

from lico.core.contrib.client import Client
from lico.core.contrib.permissions import AsUserRole
from lico.core.contrib.views import APIView

logger = logging.getLogger(__name__)


class FileStatusView(APIView):
    permission_classes = (AsUserRole,)

    def get(self, request):
        user = request.user
        try:
            client = Client().filesystem_client(user=user)
            fs_res = client.path_exists(user.workspace)
            fs_data = {'status': 'active', 'msg': ''} if fs_res \
                else {'status': 'inactive', 'msg': "WORKSPACE_ACCESS_ERROR"}
        except Exception:
            logger.exception('Error get file system working message.')
            fs_data = {'status': 'inactive', 'msg': "FS_ERROR"}

        return Response(data=fs_data)
