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

import json
import logging
import os

from rest_framework.response import Response

from lico.core.contrib.views import APIView

from ..models.template_job import TemplateJob
from ..utils.common import convert_myfolder

logger = logging.getLogger(__name__)


class EntranceURLView(APIView):
    def get(self, request, job_id):
        user = request.user
        try:
            job_info = TemplateJob.objects.get(
                username=user.username,
                job_id=job_id
            ).as_dict()
            job_json = json.loads(job_info['json_body'])

            from lico.core.contrib.client import Client
            client = Client()
            fopr = client.filesystem_client(user=user)
            entrance_uri_path = convert_myfolder(
                fopr,
                user,
                os.path.join(
                    job_json['parameters']['job_workspace'],
                    f"entrance_uri_{job_json['parameters']['job_uuid']}.json"
                )
            )
            job_content, _ = fopr.read_content(entrance_uri_path)

            return Response(json.loads(job_content))
        except KeyError as e:
            logger.warning('Failed to get job_uuid from job template '
                           'parameters, reason: %s' % e)
            return Response({"entrance_uri": ''})
        except Exception as e:
            logger.exception('Failed to get entrance_url, reason: %s' % e)
            return Response({"entrance_uri": ''})
