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

from lico.core.contrib.authentication import RemoteApiKeyAuthentication
from lico.core.contrib.views import APIView

from ..helpers.res_summary import QueryRes

logger = logging.getLogger(__name__)


class NodeResourceDisplayView(APIView):

    def get(self, request):
        params = request.query_params
        query_res = QueryRes(
            filter_type=params['filter_type'],
            filter_value=params['filter_value'])

        return Response({"data": query_res.data_to_portal})


class NodeResourceDictView(APIView):
    authentication_classes = (
        RemoteApiKeyAuthentication,
    )

    def get(self, request):
        query_res = QueryRes(
            filter_type="all",
            filter_value="all",
            is_dict=True)

        return Response({"data": query_res.data_to_portal})
