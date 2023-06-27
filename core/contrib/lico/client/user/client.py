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

from dateutil.tz import tzutc

from lico.client.contrib.client import BaseClient
from lico.core.contrib.dataclass import User

logger = logging.getLogger(__name__)


class UserClient(BaseClient):
    app = 'user'

    def get_user_list(self, **kwargs):
        response = self.get(
            self.get_url('list/'),
            params={
                key: str(value.timestamp())
                for key, value in kwargs.items()
            },
        )
        return [
            User(
                username=user_dict['username'],
                role=user_dict['role'],
                date_joined=datetime.fromtimestamp(
                    user_dict['date_joined'], tz=tzutc()
                )
            )
            for user_dict in response
        ]

    def get_group_user_list(self, name):
        try:
            import grp
            import pwd

            gid = grp.getgrnam(name).gr_gid
            return list(
                {
                    pwd_struct.pw_name for pwd_struct in pwd.getpwall()
                    if pwd_struct.pw_gid == gid
                } & {
                    user.username
                    for user in self.get_user_list()
                }
            )
        except KeyError:
            logger.warning(
                "Cannot find group named %s", name, exc_info=True
            )
            return []
