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

from lico.core.contrib.permissions import (
    AsAdminRole, AsUserRole, SchedulerPermission,
)

from .views.apikey import ApiKeyGenerateView, ApiKeyTestView, ApiKeyView
from .views.auth import AuthView
from .views.group import GroupDetailView, GroupListView
from .views.lock import FullLockView, LockView
from .views.passwd import ChangePasswordView, ModifyPasswordView
from .views.user import (
    UserDataTableView, UserDetailView, UserExportView, UserImportDetailView,
    UserImportView, UserListView,
)

urlpatterns = [
    path('apikey/generate/', ApiKeyGenerateView.as_view()),
    path('apikey/', ApiKeyView.as_view()),
    path('apikey/test/', ApiKeyTestView.as_view()),

    path('auth/', AuthView.as_view()),
    path('login/', AuthView.as_view(
        permission_classes=(AsAdminRole | (AsUserRole & SchedulerPermission),),
    )),

    path('password/', ChangePasswordView.as_view()),
    path('<int:pk>/password/', ModifyPasswordView.as_view()),

    path('<int:pk>/lock/', LockView.as_view()),
    path('<int:pk>/full-lock/', FullLockView.as_view()),

    path('group/', GroupListView.as_view()),
    path('group/<str:name>/', GroupDetailView.as_view()),

    path('', UserDataTableView.as_view()),
    path('list/', UserListView.as_view()),
    path('<int:pk>/', UserDetailView.as_view()),
    path('export/', UserExportView.as_view()),
    path('import/', UserImportView.as_view()),
    path('import/detail/', UserImportDetailView.as_view()),
]
