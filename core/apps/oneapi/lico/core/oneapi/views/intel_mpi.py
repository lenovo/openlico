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

from lico.core.contrib.schema import json_schema_validate
from lico.core.contrib.views import APIView

from ..utils.intel_mpi import (
    get_mpi_info, get_mpi_map_info, get_mpi_openmp_info,
)

# from rest_framework.views import APIView


logger = logging.getLogger(__name__)


class IntelMpiView(APIView):

    @json_schema_validate({
        "type": "object",
        "properties": {
            "run_mode": {"type": "string"},
            "type": {"type": "string"},
            "procset": {"type": "string"},
            "shift": {"type": "number"},
            "preoffset": {"type": "number"},
            "postoffset": {"type": "number"},
            "size": {"type": "number"},
            "layout": {"type": "string"},
            "cores_per_socket": {"type": "number"},
            "hyper_threading": {"type": "boolean"},
            "sockets_per_node": {"type": "number"},
            "map": {"type": 'string'}
        },
        "required": ["run_mode", "cores_per_socket", "hyper_threading",
                     "sockets_per_node"]
    })
    def post(self, request):
        data1 = request.data
        run_mode = data1['run_mode']
        response = {}

        logger.debug("run_mode={}".format(run_mode))

        if run_mode == 'mpi':
            mpi_type = data1['type']
            if mpi_type == 'customize':
                data = get_mpi_info(
                    list_procset=data1['procset'],
                    list_grain=data1['grain'],
                    list_shift=data1['shift'],
                    list_preoffset=data1['preoffset'],
                    list_postoffset=data1['postoffset'],
                    cores_per_socket=data1['cores_per_socket'],
                    sockets_per_node=data1['sockets_per_node'],
                    hyper_threading=data1['hyper_threading']
                )
            else:
                data = get_mpi_map_info(
                    list_procset=data1['procset'],
                    list_map=data1['type'],
                    cores_per_socket=data1['cores_per_socket'],
                    sockets_per_node=data1['sockets_per_node'],
                    hyper_threading=data1['hyper_threading']
                )

            response['affinity_env'] = data[0]
            response['cpuinfo'] = data[1]
            response['bind'] = data[2]
        else:
            data = get_mpi_openmp_info(
                domain_size=data1['size'],
                domain_layout=data1['layout'],
                cores_per_socket=data1['cores_per_socket'],
                hyper_threading=data1['hyper_threading'],
                sockets_per_node=data1['sockets_per_node']
            )
            response['affinity_env'] = data[0]
            response['cpuinfo'] = data[1]
            response['bind'] = data[2]

        return Response(response)
