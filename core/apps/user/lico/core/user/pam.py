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
from pamela import PAMError

from .exceptions import ModifyPasswordFailed

logger = logging.getLogger(__name__)


def auth(username: str, password: str):
    from pamela import authenticate, check_account, open_session
    authenticate(username, password,  service=settings.USER.PAM.SERVICE)

    try:
        check_account(username, service=settings.USER.PAM.SERVICE)
    except PAMError:
        logger.exception('Fail to call pam service "check_account"')

    try:
        open_session(username, service=settings.USER.PAM.SERVICE)
    except PAMError:
        logger.exception('Fail to call pam service "open_session"')


def change_password(username: str, password: str):
    from pamela import change_password
    try:
        change_password(username, password, service=settings.USER.PAM.SERVICE)
    except PAMError as e:
        raise ModifyPasswordFailed from e


class PamAuthBackend:
    def authenticate(
        self, request, user, password,
        *args, **kwargs
    ):
        username = user.username
        from pamela import PAMError
        try:
            auth(username, password)
        except PAMError:
            logger.warning(
                'Invalid user[ %s ]', username,
                exc_info=True
            )
            return None
        else:
            return user
