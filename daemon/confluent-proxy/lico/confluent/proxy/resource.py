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

import falcon
from falcon.errors import HTTPBadRequest

logger = logging.getLogger(__name__)


class Console:
    def __init__(self, client):
        self.client = client

    def on_post(self, req, resp, name):
        try:
            body = req.media
        except HTTPBadRequest:
            body = {}

        result = self.client.create_kvm_console(
            name,
            head={
                'CONFLUENTASYNCID': req.get_header('ConfluentAsyncId'),
                'CONFLUENTREQUESTID': req.get_header('ConfluentRequestId'),
                'accept': 'application/json'
            },
            body=body
        )

        resp.status = getattr(
            falcon,
            f'HTTP_{result.status_code}'
        )
        resp.media = result.json()


class Shell:
    def __init__(self, client):
        self.client = client

    def on_post(self, req, resp, name):
        try:
            body = req.media
        except HTTPBadRequest:
            body = {}

        result = self.client.create_ssh_session(
            name,
            head={
                'CONFLUENTASYNCID': req.get_header('ConfluentAsyncId'),
                'CONFLUENTREQUESTID': req.get_header('ConfluentRequestId'),
                'accept': 'application/json'
            },
            body=body
        )

        resp.status = getattr(
            falcon,
            'HTTP_{}'.format(result.status_code)
        )
        resp.media = result.json()


class Async:
    def __init__(self, client):
        self.client = client

    def on_post(self, req, resp):
        try:
            body = req.media
        except HTTPBadRequest:
            body = {}

        result = self.client.create_async(
            head={
                'accept': 'application/json'
            },
            body=body
        )

        if result is None:
            resp.status = falcon.HTTP_INTERNAL_SERVER_ERROR
        else:
            resp.status = getattr(
                falcon,
                f'HTTP_{result.status_code}'
            )
            try:
                resp.media = result.json()
            except Exception:
                resp.body = result.text
                logger.info('No data for async', exc_info=True)
