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
from django.conf import settings
from django.urls import path, re_path

from ..views.node import (
    HostNameAPIView, JobRunningNodeResourceHeatView, NodeEditorFixturesView,
    NodeHardwareView, NodeHealthView, NodesByHardwareView,
)
from ..views.tendency import (
    cpu, energy, gpu, load, memory, network, temperature,
)

category = r'(?P<category>hour|day|week|month)'
category_gpu = r'(?P<category>util|memory|temperature)'
hostname = r'(?P<hostname>.[^/]+)'

urlpatterns = [
    re_path(r'^{0}/tendency/{1}/energy/$'.format(hostname, category),
            energy.NodeHistoryEnergyView.as_view()),

    re_path(r'^{0}/tendency/{1}/load/$'.format(hostname, category),
            load.NodeHistoryLoadView.as_view()),

    re_path(r'^{0}/tendency/{1}/cpu/$'.format(hostname, category),
            cpu.NodeHistoryCpuView.as_view()),

    re_path(r'^{0}/gpu/(?P<index>[0-9]+)/tendency/'
            r'(?P<time_unit>hour|day|week|month)/{1}/$'
            .format(hostname, category_gpu),
            gpu.NodeHistoryGpuView.as_view()),

    re_path(r'^{0}/tendency/{1}/temperature/$'.format(hostname, category),
            temperature.NodeHistoryTemperatureView.as_view()),

    re_path(r'^{0}/tendency/{1}/memory/$'.format(hostname, category),
            memory.NodeHistoryMemoryView.as_view()),

    re_path(r'^{0}/tendency/{1}/network/$'.format(hostname, category),
            network.NodeHistoryNetworkView.as_view()),

    re_path(r'^{0}/tendency/{1}/ib/$'.format(hostname, category),
            network.NodeHistoryIbView.as_view()),
    path('', NodeHardwareView.as_view()),
    path('health/detail/', NodeHealthView.as_view()),
    path('host/detail/', HostNameAPIView.as_view()),
    path('node-editor-fixtures/', NodeEditorFixturesView.as_view()),
    path('nodes-by-hardware/', NodesByHardwareView.as_view()),

    # return job running node cpu/memory resource
    re_path(r'^(?P<category>cpu|memory)/latest/util/$',
            JobRunningNodeResourceHeatView.as_view()),
    re_path(r'^{0}/cpu/tendency/{1}/$'.format(hostname, category),
            cpu.JobRunningNodeUtilHistoryView.as_view()),
    re_path(r'^{0}/memory/tendency/{1}/$'.format(hostname, category),
            memory.JobRunningNodeUtilHistoryView.as_view()),
]
# 'cluster' means to use the monitor function.
if 'cluster' in settings.MONITOR.TARGETS:
    from ..views.node import NodeProcessView

    urlpatterns += [
        re_path(
            r'^{0}/process/$'.format(hostname), NodeProcessView.as_view()
        ),
    ]
