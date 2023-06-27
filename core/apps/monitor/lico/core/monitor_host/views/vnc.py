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

import base64
import re
from hashlib import sha256

import attr
from rest_framework.response import Response
from rest_framework.status import HTTP_404_NOT_FOUND

from lico.core.contrib.views import APIView
from lico.core.monitor_host.models import VNC


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


@attr.s(frozen=True)
class VncSession:
    username: str = attr.ib(kw_only=True)
    pid: int = attr.ib(kw_only=True)
    name: str = attr.ib(kw_only=True)
    port: int = attr.ib(kw_only=True)
    display: int = attr.ib(kw_only=True)
    host: str = attr.ib(kw_only=True)

    id: str = attr.ib(init=False)
    token: str = attr.ib(init=False)

    def __attrs_post_init__(self):
        object.__setattr__(
            self, 'id',
            sha256(':'.join([
                self.username,
                str(self.pid),
                self.name,
                str(self.port),
                str(self.display),
                self.host,
            ]).encode()).hexdigest()
        )
        object.__setattr__(
            self, 'token',
            encode_base64url(
                f'{self.host}:{self.port}'.encode('utf-8')
            ).decode()
        )

    def as_dict(self):
        return attr.asdict(self)


class VNCBaseView(APIView):

    def get_session_data(self):
        sessions = []
        for vnc_obj in VNC.objects.iterator():
            vnc_dict = {}
            hostname = vnc_obj.monitor_node.hostname
            detail = vnc_obj.detail
            vnc_dict['username'] = detail['user']
            vnc_dict['pid'] = detail['pid']
            vnc_dict['name'] = hostname + ':' + str(vnc_obj.index)
            vnc_dict['port'] = detail['port']
            vnc_dict['host'] = hostname
            vnc_dict['display'] = int(vnc_obj.index)
            sessions.append(VncSession(**vnc_dict))
        return sessions


class VncManagerList(VNCBaseView):

    def get(self, request, username=None):
        sessions = self.get_session_data()
        if username is None:
            return Response({'data': [s.as_dict() for s in sessions]})
        return Response(
            {'data': [s.as_dict() for s in sessions if s.username == username]}
        )


class VncManagerDetail(VNCBaseView):

    def on_get(self, request, name=None):
        sessions = self.get_session_data()
        session_detail = {}
        if name is not None:
            for session in sessions:
                if session.name == name:
                    session_detail = session.as_dict()
                    break
        if not session_detail:
            return Response(status=HTTP_404_NOT_FOUND)
        return Response({'data': session_detail})
