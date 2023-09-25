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


class JobComment(object):
    def __init__(self, job_id):
        self._job_id = job_id

    def get_comment(self):
        return 'LICO-'+str(self._job_id)

    def get_job_id(self):
        return self._job_id

    @classmethod
    def from_comment(cls, comment):
        if comment:
            items = comment.split('-')
            if len(items) == 2 and items[0] == 'LICO':
                return JobComment(int(items[1]))
            else:
                return None
        else:
            return None
