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

from lico.core.accounting.utils import get_gresource_codes
from lico.core.contrib.views import InternalAPIView

logger = logging.getLogger(__name__)


class InternalGreSourceView(InternalAPIView):
    def get(self, request):
        return Response(get_gresource_codes())
