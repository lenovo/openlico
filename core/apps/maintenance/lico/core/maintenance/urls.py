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

from .views.node_resource_views import (
    NodeResourceDictView, NodeResourceDisplayView,
)
from .views.process_terminate_views import ProcessTerminateView

urlpatterns = [
    path('nodes/resource/', NodeResourceDisplayView.as_view()),
    path('nodes/resource_usage/', NodeResourceDictView.as_view()),
    path('process/terminate/', ProcessTerminateView.as_view()),
]
