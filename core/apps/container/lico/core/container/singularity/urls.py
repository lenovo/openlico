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
    BuildImageDetailView, BuildImageEnsure, BuildImageView, ImageDetailView,
    ImageDownload, ImageListView, ImageReupload, PrivateImageEnsure,
    SearchSingularityImageList, SystemImageEnsure, SystemImageListView,
)

urlpatterns = [
    path('', ImageListView.as_view()),
    path('system/', SystemImageListView.as_view()),
    path('<int:pk>/', ImageDetailView.as_view()),
    path('reupload/<int:pk>/', ImageReupload.as_view()),
    path('download/<int:pk>/', ImageDownload.as_view()),
    path('ensure/system/<str:name>/', SystemImageEnsure.as_view()),
    path('ensure/private/<str:name>/', PrivateImageEnsure.as_view()),
    path('search/', SearchSingularityImageList.as_view()),
    path('build/', BuildImageView.as_view()),
    path('build/state/', BuildImageDetailView.as_view()),
    path('build/ensure/', BuildImageEnsure.as_view())
]
