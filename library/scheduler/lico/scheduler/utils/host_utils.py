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

from collections import defaultdict
from datetime import datetime

from dateutil.relativedelta import relativedelta
from dateutil.tz import tzlocal

MEMORY_UNIT = defaultdict(
        lambda: 0, {
            'K': 1,
            'M': 1024,
            'G': 1024 * 1024,
            'T': 1024 * 1024 * 1024
        }
    )


def datetime_to_ym_timestamp(dt, months_delta=0):
    valid_dt = dt if dt else datetime.now(tz=tzlocal())
    valid_dt = valid_dt - relativedelta(months=months_delta)
    ym_dt = valid_dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return int(ym_dt.timestamp())
