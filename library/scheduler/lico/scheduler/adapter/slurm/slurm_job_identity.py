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

import json
from datetime import datetime

import attr
from dateutil.tz import tzutc

from lico.scheduler.base.exception.job_exception import (
    InvalidJobIdentityStringException,
)
from lico.scheduler.base.job.job_identity import IJobIdentity
from lico.scheduler.utils.host_utils import datetime_to_ym_timestamp


@attr.s(frozen=True, slots=True)
class JobIdentity(IJobIdentity):
    scheduler_id: str = attr.ib()
    submit_time: datetime = attr.ib()

    def get_display(self) -> str:
        return str(self.scheduler_id)

    def to_string(self):
        return json.dumps({
            'scheduler_id': self.scheduler_id,
            'submit_time': str(
                datetime_to_ym_timestamp(self.submit_time)
            )
        })

    def to_alternative_string(self):
        return json.dumps({
            'scheduler_id': self.scheduler_id,
            'submit_time': str(
                datetime_to_ym_timestamp(self.submit_time, months_delta=1)
            )
        })

    @classmethod
    def from_string(cls, identity_str):
        identity = json.loads(identity_str)
        for key in ('scheduler_id', 'submit_time'):
            if not identity.get(key).isdigit():
                raise InvalidJobIdentityStringException

        submit_time_dt = datetime.utcfromtimestamp(
            int(identity['submit_time'])
        ).replace(tzinfo=tzutc())
        return cls(
            scheduler_id=identity['scheduler_id'],
            submit_time=submit_time_dt
        )
