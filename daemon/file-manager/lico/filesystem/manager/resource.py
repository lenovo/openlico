# -*- coding: utf-8 -*-
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

import datetime
import logging
import os
from urllib.parse import quote

import falcon
from dateutil.tz import tzutc

from .connector import FilesConnector
from .imjoy_elfinder.api_const import (
    API_DIRS, API_NAME, API_TARGETS, API_UPLOAD, API_UPLOAD_PATH,
)
from .plugin import jwt_auth
from .utils import get_all, get_one

logger = logging.getLogger(__name__)


def _file_handle(request, response, adatper, upload_max_size):
    connector = FilesConnector(
        request.user, adatper, upload_max_size=upload_max_size
    )
    # fetch only needed GET/POST parameters
    http_request = {}
    form = request.params

    for field in connector.http_allowed_parameters:
        if field in form:
            # Russian file names hack
            if field == API_NAME:
                http_request[field] = get_one(form, field).encode("utf-8")

            elif field == API_TARGETS:
                http_request[field] = get_all(form, field)

            elif field == API_DIRS:
                http_request[field] = get_all(form, field)

            elif field == API_UPLOAD_PATH:
                http_request[field] = get_all(form, field)
            elif field == API_UPLOAD_PATH:
                http_request[field] = get_all(form, field)

            # handle CGI upload
            elif field == API_UPLOAD:
                http_request[field] = get_all(form, field)
            else:
                http_request[field] = get_one(form, field)

    # run connector with parameters
    run_connector(response, connector, http_request, request)


def run_connector(response, connector, http_request, request):
    status, header, con_response = connector.run(http_request)

    if status == 200 and "__send_file" in con_response:
        # send file
        file_path = con_response["__send_file"]
        if os.path.exists(file_path) and not os.path.isdir(file_path):
            response.set_stream(open(file_path, "rb"), 32768)
            response.content_length = os.path.getsize(file_path)
            response.downloadable_as = quote(os.path.basename(file_path))
            response.content_type = 'application/octet-stream'
            response.last_modified = datetime.datetime.fromtimestamp(
                os.path.getmtime(file_path), tz=tzutc()
            )
            response.etag = "%s-%s-%s" % (
                os.path.getmtime(file_path),
                os.path.getsize(file_path),
                hash(file_path),
            )
        else:
            response.data = "Unable to find: {}".format(request.path_info)
    else:
        # get connector output and print it out
        try:
            del header["Connection"]
        except KeyError:
            pass
        response.status = getattr(
            falcon, f'HTTP_{status}', falcon.HTTP_200
        )
        response.set_headers(header)
        if "__text" in con_response:
            # output text
            response.data = con_response["__text"]
        else:
            # output json
            response.set_headers(
                {'content-type': 'application/json'}
            )
            response.media = con_response


class FileManager(object):
    def __init__(self, adapter, upload_max_size='5'):
        self.adapter = adapter
        self.upload_max_size = int(upload_max_size) * 1024 * 1024 * 1024

    def on_get(self, request, response):
        jwt_auth(request, self.adapter)
        _file_handle(request, response, self.adapter, self.upload_max_size)

    def on_post(self, request, response):
        jwt_auth(request, self.adapter)
        _file_handle(request, response, self.adapter, self.upload_max_size)
