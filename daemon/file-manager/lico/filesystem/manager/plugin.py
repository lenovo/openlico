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

import logging

import falcon

logger = logging.getLogger(__name__)


def jwt_auth(req, adapter):
    try:
        payload = req.env['X-LICO-JWT-PAYLOAD']
    except KeyError as e:
        logger.exception('Authentication credentials were not provided.')
        raise falcon.HTTPUnauthorized(
            description='Authentication credentials were not provided.'
        ) from e

    try:
        username = payload['sub']
        req.user = adapter.get_user_info(username)
    except Exception as e:
        logger.exception('User not exists')
        raise falcon.HTTPUnauthorized(
            description='User does not exists.'
        ) from e
