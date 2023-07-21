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

from django.urls import path

from .views.openapi import (
    InstanceShareUrl, OpenApiProjectDetail, OpenApiProjectList,
    ToolInstanceInfo, ToolList, ToolSettings, ToolSubmit,
)
from .views.views import (
    CloudToolSubmit, InstanceDetail, ProjectDetail, ProjectList, SettingDetail,
    SettingList, ShareUrl, ShareView,
)

urlpatterns = [
    path('project/', ProjectList.as_view()),
    path('project/<int:pk>/', ProjectDetail.as_view()),
    path('setting/', SettingList.as_view()),
    path('setting/<int:pk>/', SettingDetail.as_view()),
    path('', CloudToolSubmit.as_view()),
    path('instance/<int:pk>/', InstanceDetail.as_view()),
    path('shareurl/', ShareUrl.as_view()),
    path('share/', ShareView.as_view()),

    # openapi
    path('openapi/v1/project/', OpenApiProjectList.as_view()),
    path('openapi/v1/project/<int:pk>/', OpenApiProjectDetail.as_view()),
    path('openapi/v1/project/tool/', ToolList.as_view()),
    path(
        'openapi/v1/project/<int:project_id>/<str:tool_code>/settings/',
        ToolSettings.as_view()
    ),
    path(
        'openapi/v1/project/<int:project_id>/<str:tool_code>/submit/',
        ToolSubmit.as_view()
    ),
    path(
        'openapi/v1/project/<int:project_id>/<str:tool_code>/instance/',
        ToolInstanceInfo.as_view()
    ),
    path(
        'openapi/v1/project/<int:project_id>/<str:tool_code>/shareurl/',
        InstanceShareUrl.as_view()
    )
]
