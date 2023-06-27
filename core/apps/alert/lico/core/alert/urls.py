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

from .views import (
    AlertCountView, AlertReportDownload, AlertReportReview, AlertView,
    CommentView, NodeAlertView, PolicyDetailView, PolicyView, ScriptView,
    TargetDetailView, TargetView,
)

urlpatterns = [
    path('target/', TargetView.as_view()),
    path('target/<int:pk>/', TargetDetailView.as_view()),

    path('policy/', PolicyView.as_view()),
    path('policy/<int:pk>/', PolicyDetailView.as_view()),

    path('script/', ScriptView.as_view()),

    path('', AlertView.as_view()),
    path('comment/<int:pk>/', CommentView.as_view()),

    path('report/', AlertReportReview.as_view()),
    path('report/<str:filename>/', AlertReportDownload.as_view()),

    path('node/<str:hostname>/', NodeAlertView.as_view()),

    path('count/',  AlertCountView.as_view()),

]
