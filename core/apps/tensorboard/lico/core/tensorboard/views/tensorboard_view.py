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

from django.db.transaction import atomic
from django.utils import timezone
from rest_framework.response import Response

from lico.core.contrib.schema import json_schema_validate
from lico.core.contrib.views import APIView
from lico.core.tensorboard.models import HeartBeat

from ..tensorboard import Tensorboard

logger = logging.getLogger(__name__)


class TensorBoardView(APIView):
    @json_schema_validate({
        "type": "object",
        "properties": {
            'logdir': {
                "type": "string",
                "minLength": 1
            },
            "job_queue": {
                "type": "string",
                "minLength": 1
            },
            "job_template_code": {
                "type": "string",
            }

        },
        "required": ["logdir", 'job_template_code', 'job_queue']
    })
    def post(self, request):
        return Response({
            'data': Tensorboard().create_job(request)})


class HeartBeatView(APIView):
    permission_classes = ()

    @atomic
    def post(self, request, uuid):
        heart = HeartBeat.objects.select_for_update().get(uuid=uuid)
        heart.recent_time = timezone.now()
        heart.save()

        return Response()

    def get(self, request, uuid):
        heart = HeartBeat.objects.get(uuid=uuid)
        from lico.core.contrib.client import Client
        client = Client().job_client(username=request.user.username)
        job_info = client.query_job(heart.job_id)
        data = dict(status='creating', base_url='')
        if job_info['state'].lower() == 'c' or \
                job_info['operate_state'] == 'cancelled':
            data.update(status='off')
        elif job_info['state'].lower() == 'r':
            base_url = Tensorboard().get_base_url(
                request.user, heart.port, job_info)
            data.update(status='on', base_url=base_url)

        return Response({'data': data})
