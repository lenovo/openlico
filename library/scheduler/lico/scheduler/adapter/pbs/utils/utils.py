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
import logging
from datetime import datetime

from lico.scheduler.base.exception.job_exception import QueryJobFailedException
from lico.scheduler.utils.cmd_utils import exec_oscmd_with_login

logger = logging.getLogger(__name__)


def get_job_submit_datetime(scheduler_id, config):
    args = ["qstat", "-xf", "-F", "json", scheduler_id]
    rc, out, err = exec_oscmd_with_login(args, config.timeout)
    try:
        data = json.loads(out)
    except (json.JSONDecodeError, TypeError) as exc:
        logger.error(
            f"Get job {scheduler_id} detail info failed, "
            f"job_identity is invalid. Error message is: {exc}"
        )
        raise QueryJobFailedException(str(exc))
    mask = '%a %b  %d %H:%M:%S %Y'
    return datetime.strptime(data["Jobs"][scheduler_id]['ctime'], mask)


def get_job_query_data(cmd, timeout):
    rc, out, err = exec_oscmd_with_login(cmd, timeout)
    try:
        data = json.loads(out)
    except (json.JSONDecodeError, TypeError) as exc:
        logger.error(f"Query recent jobs failed: {exc}")
        raise QueryJobFailedException(str(exc))
    return data
