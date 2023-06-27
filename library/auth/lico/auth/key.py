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

from datetime import datetime, timedelta

import attr
from dateutil.tz import tzutc


@attr.s(slots=True)
class Key:
    key = attr.ib(default=None)
    expire_time = attr.ib()

    @expire_time.default
    def key_default(self):
        return datetime.now(tzutc()) + timedelta(days=3)

    def is_valid(self):
        return self.expire_time > datetime.now(tzutc())


@attr.s(slots=True)
class KeyGroup:
    latest = attr.ib(factory=Key)
    history = attr.ib(factory=list)
    token_expire_minute = attr.ib(default=60)
    key_expire_day = attr.ib(default=3)

    def update(self, key):
        # set lastest key and update history
        now = datetime.now(tzutc())
        if self.latest.key == key:
            self.latest.expire_time = now + timedelta(
                days=self.key_expire_day)
        else:
            if self.latest.key:
                self.latest.expire_time = now + timedelta(
                    minutes=self.token_expire_minute * 2)
                self.history += [self.latest]
            self.latest = Key(key=key,
                              expire_time=now + timedelta(
                                  days=self.key_expire_day))

    def clear_expired(self):
        # delete key in history if it expires
        for key in self.history:
            if not key.is_valid():
                self.history.remove(key)
