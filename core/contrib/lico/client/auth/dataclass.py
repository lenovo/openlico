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
from datetime import datetime
from functools import partial
from typing import Optional

import attr
from dateutil.tz import tzutc

logger = logging.getLogger(__name__)


class LocalUserNotFound(Exception):
    pass


class RequireUserContext(Exception):
    pass


@attr.s(frozen=True)
class User:
    ADMIN_ROLE = 300
    OPERATOR_ROLE = 200
    USER_ROLE = 100

    username: str = attr.ib(kw_only=True)
    date_joined: datetime = attr.ib(
        kw_only=True,
        factory=partial(datetime.now, tz=tzutc())
    )

    role: int = attr.ib(
        validator=attr.validators.in_([ADMIN_ROLE, OPERATOR_ROLE, USER_ROLE]),
        default=USER_ROLE, kw_only=True
    )
    email: Optional[str] = attr.ib(kw_only=True, default=None)

    @property
    def is_admin(self) -> bool:
        return self.role >= self.ADMIN_ROLE

    @property
    def is_operator(self) -> bool:
        return self.role >= self.OPERATOR_ROLE

    @property
    def is_user(self) -> bool:
        return self.role >= self.USER_ROLE

    def require_context(self):
        raise RequireUserContext


@attr.s(frozen=True)
class HostGroup:
    gid: Optional[int] = attr.ib(kw_only=True, default=None)
    name: Optional[str] = attr.ib(kw_only=True, default=None)

    _group = attr.ib(init=False, default=None)

    def __attrs_post_init__(self):
        if self.name is None and self.gid is not None:
            from grp import getgrgid
            try:
                _group = getgrgid(self.gid)
            except KeyError:
                logger.warning(
                    'Could not find group info from nss: %s', self.gid
                )
                object.__setattr__(self, 'name', f'{self.gid}')
            else:
                object.__setattr__(self, 'name', _group.gr_name)

                object.__setattr__(self, '_group', _group)


@attr.s(frozen=True)
class HostPasswd:
    username: str = attr.ib(kw_only=True)

    workspace: Optional[str] = attr.ib(init=False, default=None)
    uid: Optional[int] = attr.ib(init=False, default=None)
    gid: Optional[int] = attr.ib(init=False, default=None)

    group: HostGroup = attr.ib(init=False)

    _passwd = attr.ib(init=False, default=None)

    def __attrs_post_init__(self):
        from pwd import getpwnam
        try:
            _passwd = getpwnam(self.username)
        except KeyError:
            logger.warning(
                'Could find user info from nss: %s',
                self.username, exc_info=True
            )
            object.__setattr__(
                self, 'group', HostGroup(
                    gid=self.gid, name=None
                )
            )
        else:
            object.__setattr__(self, "workspace", _passwd.pw_dir)
            object.__setattr__(self, 'uid', _passwd.pw_uid)
            object.__setattr__(self, 'gid', _passwd.pw_gid)

            object.__setattr__(self, 'group', HostGroup(gid=self.gid))

            object.__setattr__(self, '_passwd', _passwd)


@attr.s(frozen=True)
class HostUser(User, HostPasswd):
    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        if self._passwd is None:
            raise LocalUserNotFound
