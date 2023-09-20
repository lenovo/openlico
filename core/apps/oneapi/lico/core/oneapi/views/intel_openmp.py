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

import numpy as np
from rest_framework.response import Response

from lico.core.contrib.schema import json_schema_validate
# from rest_framework.views import APIView
from lico.core.contrib.views import APIView

from ..utils.intel_openmp import change_format, drop_dim, transpose

logger = logging.getLogger(__name__)


class OpenMPView(APIView):

    @json_schema_validate({
        "type": "object",
        "properties": {
            "sockets_per_node": {"type": "integer"},
            "cores_per_socket": {"type": "integer"},
            "hyper_threading": {"type": "boolean"},
            "granularity": {"type": "string"},
            "bind_type": {"type": "string"},
            "permute": {"type": "integer"},
            "offset": {"type": "integer"},
        },
        "required": []
    })
    def post(self, request):

        sockets_per_node = request.data.get("sockets_per_node", 2)
        cores_per_socket = request.data.get("cores_per_socket", 8)
        hyper_threading = request.data.get("hyper_threading", True)
        granularity = request.data.get("granularity", "core")
        bind_type = request.data.get("bind_type", "none")
        permute = request.data.get("permute", 0)
        offset = request.data.get("offset", 0)

        data = dict()

        if hyper_threading:
            hyper_thread = 2
        else:
            hyper_thread = 1

        total_cores = sockets_per_node * cores_per_socket * hyper_thread

        # Generate the OS system logical CPU number
        arr = np.arange(total_cores).reshape(
            hyper_thread, cores_per_socket * sockets_per_node).T.reshape(
            sockets_per_node, cores_per_socket, hyper_thread)
        arr = arr.tolist()
        logger.debug("arr={}".format(arr))
        os_proc = arr
        data["cpuinfo"] = arr

        affinity_env = dict()
        KMP_AFFINITY = "granularity=" + granularity + "," + bind_type \
                       + "," + str(permute) + "," + str(offset)
        affinity_env["KMP_AFFINITY"] = KMP_AFFINITY
        data["affinity_env"] = affinity_env

        tid_bind = dict()
        if bind_type == "scatter" or bind_type == "compact":

            if bind_type == "scatter":
                per = 2 - permute
            else:
                per = permute

            for j in range(2 - per):
                arr, flag = drop_dim(arr)
                if not flag:
                    break
            logger.debug("drop_dim arr={}".format(arr))
            for i in range(per):
                arr, flag1 = transpose(arr)
                logger.debug("transpose arr={}".format(arr))
                arr, flag2 = drop_dim(arr)
                logger.debug("drop_dim arr={}".format(arr))
                if not (flag1 and flag2):
                    break

            arr = arr[offset % total_cores:] + arr[:offset % total_cores]

            tid_bind = change_format(granularity, os_proc, arr)
        else:
            kv = ",".join([str(i) for i in range(total_cores)])
            tid_bind[kv] = kv
        logger.debug("tid_bind={}".format(tid_bind))
        data["bind"] = tid_bind

        return Response(data)
