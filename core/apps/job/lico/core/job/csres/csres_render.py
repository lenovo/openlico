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

import fcntl
import logging
import os
import re
import tempfile
from collections import defaultdict
from string import Template

from ..base.job_state import JobState
from ..models import Job, JobCSRES
from .csres_exceptions import AllocatingCSResException, NoMoreCSResException

logger = logging.getLogger(__name__)


class CSResRender(object):
    def __init__(self, lock_file_directory=tempfile.tempdir):
        self._lock_file_directory = lock_file_directory
        self._csres_allocator_list = []

    def append_csres_allocator(self, allocator):
        self._csres_allocator_list.append(allocator)

    def _get_lock_filename(self, csres_code):
        lock_filename = os.path.join(
            self._lock_file_directory,
            f'lico_csres_{csres_code}.lock'
        )
        return lock_filename

    def render(self, job_id, job_content):
        render_job_content = job_content
        for allocator in self._csres_allocator_list:
            csres_code = allocator.get_csres_code()
            lock_filename = self._get_lock_filename(csres_code)
            try:
                with open(lock_filename, 'w+') as f:
                    fcntl.flock(f, fcntl.LOCK_EX)

                    cres_values = JobCSRES.objects.filter(
                        csres_code=csres_code,
                        job__state__in=JobState.get_waiting_state_values()
                    ).values_list('csres_value')
                    allocated_values = [
                        v[0] for v in cres_values if len(v) > 0 and v[0]
                    ]

                    csres_generator = CSResGenerator(
                        job_id,
                        allocator,
                        allocated_values
                    )
                    render_job_content = CSResTemplate(
                        render_job_content
                    ).substitute(
                        csres_generator
                    )
            except Exception as e:
                raise AllocatingCSResException(job_id, csres_code) from e
        return render_job_content


class CSResTemplate(Template):
    delimiter = "@@"


class CSResGenerator(defaultdict):
    def __init__(self, job_id, csres_allocator, allocated_values):
        self._job_id = job_id
        self._csres_allocator = csres_allocator
        self._csres_code = csres_allocator.get_csres_code()
        self._generator = self.csres_iterator(allocated_values)
        self._inner_dict = dict()

    def csres_iterator(self, allocated_values):
        # allocated_values = []
        while True:
            value = self._csres_allocator.next_csres_value(allocated_values)
            if value is None:
                break
            JobCSRES.objects.create(
                job=Job.objects.get(id=self._job_id),
                csres_code=self._csres_code,
                csres_value=value
            )
            logger.info(
                f"Save job-csres relation: "
                f"{self._job_id} -- {self._csres_code}"
            )
            allocated_values.append(value)
            yield value
        raise NoMoreCSResException(self._job_id, self._csres_code)

    def __missing__(self, key):  # noqa： C901
        single_ret = re.match(
            r'^lico_%s(\d+)$' % self._csres_code, key
        )
        multi_range_ret = re.match(
            r'^lico_%s(\d+)_(\d+)$' % self._csres_code, key
        )
        multi_seperate_ret = re.match(
            r'^lico_%s_(.+)$' % self._csres_code, key
        )
        # Parse res key
        try:
            csres_keys = []
            if single_ret is not None:
                # Match single allocating
                csres_keys.append(int(single_ret[1]))
            elif multi_range_ret is not None:
                # Match multi range allocating
                range_start = int(multi_range_ret[1])
                range_end = int(multi_range_ret[2])
                if range_end < range_start:
                    raise KeyError((key,))
                for idx in range(range_start, range_end + 1):
                    csres_keys.append(int(idx))
            elif multi_seperate_ret is not None:
                # Match multi separate allocating
                range_str = multi_seperate_ret[1]
                if range_str.count('_') >= 1:
                    for idx_str in range_str.split('_'):
                        csres_keys.append(int(idx_str))
            else:
                raise KeyError((key,))
        except ValueError:
            raise KeyError((key,))
        # Allocate res
        allocate_vals = []
        for key in csres_keys:
            if key not in self._inner_dict:
                self._inner_dict[key] = next(self._generator)
            allocate_vals.append(str(self._inner_dict[key]))
        self[key] = ','.join(allocate_vals)
        return self[key]
