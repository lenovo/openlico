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
from django.urls import path, re_path

from .views.easyconfig import EasyConfigParseView
from .views.modules import (
    ModuleListView, UserModuleBuildingView, UserModuleJobCountView,
    UserModuleJobView, UserModuleSearchView, UserModuleSubmitView,
)

urlpatterns = [
    path("", ModuleListView.as_view()),
    path("submit/", UserModuleSubmitView.as_view()),
    re_path("search/(?P<option>alnum|name)/", UserModuleSearchView.as_view()),
    path("easyconfig/content/", EasyConfigParseView.as_view()),
    path("job/", UserModuleBuildingView.as_view()),
    path("job_count/", UserModuleJobCountView.as_view()),
    path("job/<int:pk>/", UserModuleJobView.as_view()),
]
