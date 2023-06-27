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

from lico.core.contrib.authentication import (
    RemoteJWTInternalAuthentication, RemoteJWTWebAuthentication,
)
from lico.core.contrib.views import APIView

from ..helpers.queue_helper import (
    queue_has_gres, trans_scheduler_queue_to_dict,
)
from ..utils import get_available_queues

logger = logging.getLogger(__name__)


class QueueListView(APIView):
    authentication_classes = (
        RemoteJWTWebAuthentication,
        RemoteJWTInternalAuthentication
    )

    def get(self, request):
        gres = request.query_params.get('gres', None)
        role = request.query_params.get('role', None)

        sched_queues = get_available_queues(request, role)

        ret_q = []
        if gres:
            [ret_q.append(q) for q in sched_queues if queue_has_gres(q, gres)]
        else:
            ret_q = sched_queues
        available_queues = [
            trans_scheduler_queue_to_dict(q) for q in ret_q
        ]
        return Response(available_queues)
