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

from django.conf import settings
from rest_framework.response import Response

from lico.core.contrib.client import Client
from lico.core.contrib.schema import json_schema_validate
from lico.core.contrib.views import APIView

from ..exceptions import (
    TerminateFileConfigException, TerminateNoPermissionException,
    TerminateProcessException,
)
from ..utils import exec_oscmd, exec_ssh_oscmd

logger = logging.getLogger(__name__)


class ProcessTerminateView(APIView):

    @json_schema_validate({
        "type": "object",
        "properties": {
            "hostname": {"type": "string"},
            "pid_list": {
                "type": "array",
                "items": {"type": "string"}
            }
        },
        "required": ["hostname", "pid_list"]
    })
    def post(self, request):
        hostname = request.data['hostname']
        pid_list = request.data['pid_list']

        other_process = []

        if request.user.is_admin is not True:
            monitor_client = Client().monitor_client()
            process_list = monitor_client.get_process_info(hostname, pid_list)
            for process in process_list:
                if process.user != request.user.username:
                    other_process.append(process.pid)
            if other_process:
                raise TerminateNoPermissionException(
                    f"{request.user.username} has no permission to "
                    f"kill process {','.join(other_process)}.")
        kill_file_path = settings.MAINTENANCE.kill_file_path
        if kill_file_path:
            cmd = kill_file_path
            pid_args = f"{hostname} {str(pid_list)}"
            ret, out, err = exec_oscmd(cmd, args=pid_args.encode())
            if err:
                raise TerminateProcessException(err)
        else:
            pid_str = ' '.join(pid_list)
            cmd = ["kill", "-9", f"{pid_str}"]
            _, _, err = exec_ssh_oscmd(hostname, cmd)
            if str(err).find('No such process') >= 0:
                logger.exception(f"{hostname}:{str(err)}")
                return Response()
            elif err:
                logger.exception(err)
                raise TerminateFileConfigException

        return Response()
