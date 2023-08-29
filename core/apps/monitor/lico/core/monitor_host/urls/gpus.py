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

from django.urls import re_path

from ..views.tendency import gpu
from .nodes import category_gpu

urlpatterns = [
    re_path(
        r'^heat/latest/{0}/$'.format(category_gpu),
        gpu.NodeHeatGpuView.as_view()
    ),

    # get hostname and gpu used index list of the all nodes
    # which are running the job
    re_path(r'job/(?P<job_id>\w+)/$', gpu.JobGpuView.as_view()),
    # get hostname, gpu used index, lastest category usage of the all nodes
    # which are running the specified job
    re_path(
        r'^job/(?P<job_id>\w+\[\d+\]|\w+)/latest/(?P<category>memory|util)/$',
        gpu.JobGpuHeatView.as_view()
    )
]
