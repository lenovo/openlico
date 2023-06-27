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

from rest_framework.response import Response

from lico.core.contrib.permissions import AsOperatorRole
from lico.core.contrib.views import APIView

from ..base.job_state import JobState
from ..models import JobRunning


class RunningJobDetailView(APIView):
    permission_classes = (AsOperatorRole,)

    def get(self, request, hostname):
        runing_joblist = []
        query = JobRunning.objects.filter(
            job__state=JobState.RUNNING.value)

        for running_job in query:
            job_dict = {
                'core_num_on_node': 0,
                'gpu_num_on_node': 0
            }
            if hostname.lower() in running_job.hosts.lower().split(','):
                job = running_job.job
                job_dict['id'] = job.id
                job_dict['jobid'] = job.scheduler_id
                job_dict['jobname'] = job.job_name
                job_dict['queue'] = job.queue
                job_dict['submitter'] = job.submitter
                job_dict['starttime'] = job.start_time
                for i in job.tres.split(','):
                    key, value = i.split(':')
                    if key == 'C':
                        job_dict['core_num_on_node'] = int(float(value))
                        continue
                    if key.startswith('G/gpu'):
                        job_dict['gpu_num_on_node'] += int(float(value))
                        continue
                runing_joblist.append(job_dict)
        return Response(runing_joblist)
