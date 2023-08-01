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

from .views.entrance_url_view import EntranceURLView
from .views.tensorboard_view import HeartBeatView, TensorBoardView

urlpatterns = [
    path('', TensorBoardView.as_view()),

    path('entrance_url/<int:job_id>/', EntranceURLView.as_view()),
    path('<str:uuid>/', HeartBeatView.as_view()),
]
