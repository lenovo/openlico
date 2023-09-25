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

from rest_framework.response import Response

from lico.core.contrib.views import APIView

from ..exceptions import UserModuleException
from ..utils import EasyConfigParser, convert_myfolder, get_fs_operator

logger = logging.getLogger(__name__)


class EasyConfigParseView(APIView):

    def get(self, request):
        user = request.user
        easyconfig_path = request.query_params.get('easyconfig_path')

        fopr = get_fs_operator(user)
        complete_path = convert_myfolder(fopr, user, easyconfig_path)

        try:
            with open(complete_path, 'r') as f:
                module_info = EasyConfigParser(f.name, f.read()).parse()
                return Response(module_info)
        except FileNotFoundError as e:
            raise UserModuleException(message=e)
        except Exception as e:
            raise UserModuleException(message=e)
