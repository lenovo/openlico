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

from lico.core.accounting.charge_job import charge_job
from lico.core.contrib.schema import json_schema_validate
from lico.core.contrib.views import InternalAPIView

logger = logging.getLogger(__name__)


class ChargeJobView(InternalAPIView):
    @json_schema_validate({
        "type": "object",
        "properties": {
            "submitter": {
                "type": "string"
            },
            "queue": {
                "type": "string"
            },
            "scheduler_id ": {
                "type": "string"
            },
            "job_name": {
                "type": "string"
            },
            "submit_time": {
                "type": "integer"
            },
            "start_time": {
                "type": "integer"
            },
            "end_time": {
                "type": "integer"
            },
            "id": {
                "type": "integer"
            },
            "runtime": {
                "type": "integer"
            },
            "state": {
                "type": "string"
            },
            "tres": {
                'type': 'string'
            },
        },
        'required': [
            "submitter", "queue", "scheduler_id", "job_name", "submit_time",
            "start_time", "end_time", "id", "runtime", "state", "tres"
        ]
    })
    def put(self, request):
        datas = request.data
        if datas['state'].lower() == 'c':
            try:
                charge_job(datas)
            except Exception:
                logger.exception('Charge job failed.')
        return Response({})
