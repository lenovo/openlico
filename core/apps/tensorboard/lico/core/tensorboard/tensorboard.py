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
import uuid

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from lico.client.contrib.exception import NotFound

from .exceptions import ImageFileNotExist
from .models import HeartBeat

logger = logging.getLogger(__name__)


class Tensorboard(object):
    def prepare_parameters(self, request):
        base_params = dict(
            job_queue=request.data['job_queue'],
            job_uuid=f'le-{uuid.uuid4()}'
        )

        return base_params

    def get_port(self, ret, request):
        from lico.core.contrib.client import Client
        client = Client().job_client(username=request.user.username)
        res = client.query_job(ret['id'])

        for csres in res['job_csres']:
            if csres['csres_code'] == 'port':
                port = int(csres['csres_value'])
                break

        return port

    def get_base_url(self, user, port, job):
        import socket

        from lico.core.contrib.base64 import encode_base64url

        return encode_base64url(
            "{}:{}".format(
                socket.gethostbyname(
                    job['job_running'][0]['hosts'].split(",")[0]
                ),
                port
            ).encode()
        ).decode()

    def create_job(self, request):
        with transaction.atomic():
            heartbeats = HeartBeat.objects.filter(
                train_dir=request.data['logdir'],
                username=request.user.username).order_by('-job_id')
            for heartbeat in heartbeats:
                try:
                    from lico.core.contrib.client import Client
                    client = Client().job_client(
                        username=request.user.username
                    )
                    ret = client.query_job(heartbeat.job_id)
                except NotFound:
                    logger.warning(
                        "Query job id %s status failed.",
                        heartbeat.job_id, exc_info=True
                    )
                    continue

                if ret['state'].lower() == "r" and \
                        ret['operate_state'] != 'cancelling':
                    heartbeat.recent_time = timezone.now()
                    heartbeat.save()
                    return {
                        'uuid': heartbeat.uuid
                    }
                elif ret['operate_state'] == 'cancelling':
                    heartbeat.train_dir = ''
                    heartbeat.save()

        base_params = self.prepare_parameters(request)
        ret = self.request_job_proxy(
            request, base_params)
        port = self.get_port(ret, request)
        HeartBeat.objects.create(
            uuid=base_params['job_uuid'],
            job_id=ret['id'],
            train_dir=request.data['logdir'],
            port=port,
            username=request.user.username
        )

        return {
            'uuid': base_params['job_uuid']
        }

    @staticmethod
    def get_job_workspace(request):
        from lico.core.contrib.client import Client
        fopr = Client().filesystem_client(user=request.user)
        tensorb_path = fopr.path_join(
            os.path.dirname(request.data['logdir']), '.tensorboard')
        if not fopr.path_isdir(tensorb_path):
            fopr.makedirs(tensorb_path)
            fopr.chown(tensorb_path, request.user.uid, request.user.gid)

        return tensorb_path

    def request_job_proxy(self, request, params):
        tensorb_path = self.get_job_workspace(request)
        from lico.core.contrib.client import Client
        client = Client().container_client()

        tf2_job_code = ['ai_tensorflow2_single', 'ai_tensorflow2']

        if request.data['job_template_code'] in tf2_job_code:
            image_name = "tensorflow2-cpu"
            search_func = client.search_tensorflow2_image
        else:
            image_name = "tensorflow-cpu"
            search_func = client.search_tensorflow_image

        try:
            image_path = search_func(image_name=image_name)
        except NotFound as e:
            logger.warning(
                "%s image is not exist",
                image_name, exc_info=True
            )
            raise ImageFileNotExist from e

        params.update(
            job_workspace=tensorb_path,
            job_name='tensorboard',
            log_dir=request.data['logdir'],
            image_path=image_path,
            cores_per_node=settings.TENSORBOARD.CPU_NUM,
        )

        from lico.core.contrib.client import Client
        client = Client().template_client(username=request.user.username)
        return client.submit_template_job('ai_tensorboard', params)
