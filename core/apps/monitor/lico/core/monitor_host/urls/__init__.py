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
from django.conf import settings
from django.conf.urls import include
from django.urls import path, re_path

from ..views.cluster import ClusterOverview
from ..views.node import InternalMonitorResourceView
from ..views.rack import RackView
from ..views.report import ReportDownloadView, UtilizationReportPreview
from ..views.row import RowView
from . import cluster, gpus, groups, nodes, vnc

urlpatterns = [
    path('node/', include(nodes)),
    path('nodegroup/', include(groups)),
    path('cluster/', include(cluster)),
    path('overview/', ClusterOverview.as_view()),
    path('row/', RowView.as_view()),
    path('rack/', RackView.as_view()),
    path('gpu/', include(gpus)),
    path('vnc/', include(vnc)),


    re_path('report/(?P<category>cpu|memory|network|gpu)/',
            UtilizationReportPreview.as_view()),
    path('report/download/', ReportDownloadView.as_view()),
    path('internal/resource/<str:resource_type>/',
         InternalMonitorResourceView.as_view()),
]

# 'cluster' means to use the monitor function.
if 'cluster' in settings.MONITOR.TARGETS:
    from ..views.node import NodeProcessView

    urlpatterns += [
        path('internal/process/<str:hostname>/',
             NodeProcessView.as_view()),
    ]
