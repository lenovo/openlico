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

import base64
import logging
from os import path

from rest_framework.response import Response

from lico.core.contrib.schema import json_schema_validate
from lico.core.contrib.views import APIView

from ..helpers.fs_operator_helper import get_fs_operator

logger = logging.getLogger(__name__)


class JobLogView(APIView):

    @staticmethod
    def calculate_begin_line(first_line, number_of_lines, total_line_num):
        delta_pos = total_line_num - number_of_lines

        if first_line < 0:
            logger.error("error file line number: %s", first_line)
            begin_line = 0
        elif first_line >= delta_pos:
            begin_line = first_line
        else:
            begin_line = delta_pos

        return begin_line

    @json_schema_validate({
        'type': 'object',
        'properties': {
            "file_path": {
                'type': 'string',
                'pattern': r'^(?!/)'
                        r'(?!(?:.*/)?\.\.(?:$|/))'
                        r'[^\r\n]+$'
            },
            'line_num': {
                'type': 'string',
                'pattern': r'^\d+$'
            },
            'lines': {
                'type': 'string',
                'pattern': r'^\d+$'
            },
        },
        "required": ['file_path', 'line_num'],
    }, is_get=True)
    def get(self, request):
        user = request.user
        relative_path = request.query_params['file_path']
        workspace = request.user.workspace
        file_path = path.join(workspace, relative_path)
        start_pos = int(request.query_params['line_num'])
        number_of_lines = int(request.query_params.get('lines', 1000))

        fopr = get_fs_operator(user)

        error_resp = {
            'data': {'log': '', 'line_num': start_pos}
        }

        if not fopr.path_isfile(file_path):
            logger.error('File not exists: %s', file_path)
            return Response(error_resp)

        if not fopr.path_isreadable(file_path, user.uid, user.gid):
            logger.error('No permission: %s', file_path)
            return Response(error_resp)

        total_line_num = fopr.count_file_lines(file_path, mode='rb')

        # If 'lines' in request parameters, then return the entire file
        if 0 == number_of_lines:
            number_of_lines = total_line_num

        start_pos = self.calculate_begin_line(
            start_pos, number_of_lines, total_line_num
        )
        log, end_pos = fopr.read_content(
            file_path, start_pos, number_of_lines, mode='rb'
        )

        return Response(
            {
                'data': {
                    "log": base64.b64encode(log.strip()).decode(),
                    "line_num": end_pos
                }
            }
        )
