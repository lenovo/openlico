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

import logging

from lico.client.contrib.client import BaseClient

logger = logging.getLogger(__name__)


class Client(BaseClient):
    app = 'template'

    def submit_template_job(self, template_id, template_param_vals):
        hooks = template_param_vals.get('job_notify', [])
        req_data = {
            'template_id': template_id,
            'parameters': template_param_vals,
            'hooks': hooks
        }
        response = self.post(
            self.get_url('submitjob/'),
            json=req_data
        )
        return response

    def query_template_job(self, job_id):
        if self.username is None:
            url = 'internal/templatejob/{}/'.format(str(job_id))
        else:
            url = 'templatejob/{}/'.format(str(job_id))
        response = self.get(
            self.get_url(url)
        )
        return response

    def notify_job(self, job_info):
        req_data = job_info
        response = self.post(
            self.get_url('notifyjob/'),
            json=req_data
        )
        return response

    def get_job_template(self, template_code):
        response = self.get(
            self.get_url('jobtemplates/{}/'.format(template_code))
        )
        return response
