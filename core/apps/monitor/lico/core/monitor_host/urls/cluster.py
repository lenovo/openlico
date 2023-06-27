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

from django.urls import path, re_path

from ..views.cluster import ClusterResourceView
from ..views.tendency import cpu, gpu, memory

category = r'(?P<category>hour|day|week|month)'

urlpatterns = [
    re_path(r'^tendency/{0}/cpu/$'.format(category),
            cpu.ClusterTendencyCpuView.as_view()),
    re_path(r'^tendency/{0}/memory/$'.format(category),
            memory.ClusterTendencyMemoryView.as_view()),
    re_path(r'^tendency/{0}/gpu/util/$'.format(category),
            gpu.ClusterTendencyGpuView.as_view()),
    re_path(r'^tendency/{0}/gpu/memory/$'.format(category),
            gpu.ClusterTendencyGpuMemView.as_view()),
    path('resource/', ClusterResourceView.as_view()),
]
