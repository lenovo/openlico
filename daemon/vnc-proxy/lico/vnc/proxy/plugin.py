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
import re

from websockify.token_plugins import BasePlugin


def encode_base64url(s):
    return re.sub(
        r'=+\Z', '',
        base64.urlsafe_b64encode(s).decode()
    ).encode()


def decode_base64url(s):
    fill_num = 4 - len(s) % 4
    return base64.urlsafe_b64decode(
        s + b'=' * fill_num
    )


class LICOTokenApi(BasePlugin):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def lookup(self, token):
        vnc_info = decode_base64url(
            token.encode('utf-8')
        ).decode()
        host, port = vnc_info.split(":")
        return host, int(port)
