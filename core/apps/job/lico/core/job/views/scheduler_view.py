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
import time

from rest_framework.response import Response

from lico.core.contrib.permissions import AsUserRole
from lico.core.contrib.views import APIView

from ..exceptions import (
    QuerySchedulerLicenseFeatureException, QuerySchedulerRuntimeException,
)
from ..helpers.scheduler_helper import get_admin_scheduler, get_scheduler

logger = logging.getLogger(__name__)


class SchedulerStatusView(APIView):
    permission_classes = (AsUserRole,)

    def get(self, request):
        try:
            res = get_scheduler(user=request.user).get_status()
            if res:
                scheduler_data = {"status": "active", "msg": ""}
            else:
                scheduler_data = {
                    'status': 'inactive',
                    'msg': "SCHEDULER_ERROR"}
        except Exception:
            logger.exception('Error getting scheduler working message.')
            scheduler_data = {
                'status': 'inactive',
                'msg': "SCHEDULER_ERROR"}

        return Response(data=scheduler_data)


class SchedulerRuntimeView(APIView):
    def get(self, request):
        try:
            res = get_scheduler(user=request.user).get_runtime()
        except Exception as e:
            raise QuerySchedulerRuntimeException from e
        timestamp = int(time.time())
        return Response({
            'runtime': res,
            'timestamp': timestamp
        })


class SchedulerGresTypeView(APIView):
    permission_classes = (AsUserRole,)

    def get(self, request):
        scheduler = get_admin_scheduler()
        """
        gres_type_dict example for slurm:
        {
            "head": {"gpu:3g.20gb": 1, "gpu:2g.10gb": 2},
            "c1": {"": 2}, # "": Indicates the gpu physical card
            ...
        }

        gres_type_dict example for lsf:
        {
            "head": {"4/2": 2, "2/2": 1, "1/1": 1},
            "c1": {"2/2": 2},
            ...
        }
        """
        gres_type_dict = scheduler.get_gres_type()
        if not gres_type_dict:
            return Response(data=[])

        gres_type_set = set()
        for host, gres_type in gres_type_dict.items():
            gres_type_set = gres_type_set | set(gres_type.keys())

        gres_type_list = list(gres_type_set)

        if gres_type_list == list() or gres_type_list == ['', ]:
            return Response(data=[])
        elif '' in gres_type_list:
            gres_type_list.remove('')
        gres_type_list.insert(0, '')

        """
        Response example for slurm:
            [
                "",
                "gpu:2g.10gb",
                "gpu:3g.20gb"
            ]

        Response example for lsf:
            [
                "1/1",
                "4/2",
                "2/2"
            ]
        """
        return Response(data=gres_type_list)


class SchedulerLicenseFeatureView(APIView):
    permission_classes = (AsUserRole,)

    def get(self, request):
        """
        :param request:
        :return:
        [
            {
                "feature": "fea",
                "total": 100,
                "used": 10
            },
            ...
        ]
        """
        try:
            res = get_scheduler(user=request.user).get_license_feature()
        except Exception as e:
            raise QuerySchedulerLicenseFeatureException from e
        return Response(res or [])

