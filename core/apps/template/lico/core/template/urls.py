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

from .views.alltemplates import AllTemplatesView, CategoriesView
from .views.entrance_url_view import EntranceURLView
from .views.favorite import (
    FavoriteTemplateListView, FavoriteTemplateView, RecentTemplateView,
)
from .views.job import (
    NotifyJobView, PreviewJobView, RerunJobView, SubmitJobView,
)
from .views.lmod import ModuleListView, ModuleVerifyView
from .views.runtime import (
    RuntimeDetailView, RuntimeDistinctDetailListView, RuntimeListView,
    RuntimeVerifyView,
)
from .views.template_job import TemplateJobInternalView, TemplateJobView
from .views.templates import (
    TemplateDefaultRunTimeView, TemplateDetailView, TemplateHelpView,
    TemplateListView, TemplateLogoView, TemplateResourceView,
    TemplatesDescView,
)
from .views.user_templates import (
    UserTemplateDetailView, UserTemplateExportView, UserTemplateImportView,
    UserTemplateListView, UserTemplateLogoView, UserTemplatePublishView,
    UserTemplateUnpublishView,
)

urlpatterns = [
    # Modules and Runtime APIs
    path('modules/', ModuleListView.as_view()),
    path('modules/verify/', ModuleVerifyView.as_view()),
    path('runtime/', RuntimeListView.as_view()),
    path('runtime/<int:pk>/', RuntimeDetailView.as_view()),
    path('runtime/details/', RuntimeDistinctDetailListView.as_view()),
    path('runtime/verify/<int:pk>/', RuntimeVerifyView.as_view()),

    # System templates APIs
    path('jobtemplates/', TemplateListView.as_view()),
    path('jobtemplates/recent/', RecentTemplateView.as_view()),
    path('jobtemplates/<str:code>/', TemplateDetailView.as_view()),
    path('jobtemplates/<str:code>/logo/', TemplateLogoView.as_view()),
    path('jobtemplates/<str:code>/help/', TemplateHelpView.as_view()),
    path('jobtemplates/<str:code>_example.zip',
         TemplateResourceView.as_view()),

    # Preview and Submit template job APIs
    path('previewjob/', PreviewJobView.as_view()),
    path('submitjob/', SubmitJobView.as_view()),
    path('rerunjob/<int:jobid>/', RerunJobView.as_view()),

    # User templates APIs
    path('usertemplates/',
         UserTemplateListView.as_view()),
    path('usertemplates/<int:pk>/',
         UserTemplateDetailView.as_view()),
    path('usertemplates/<int:pk>/publish/',
         UserTemplatePublishView.as_view()),
    path('usertemplates/<int:pk>/unpublish/',
         UserTemplateUnpublishView.as_view()),
    path('usertemplates/<int:pk>/export/',
         UserTemplateExportView.as_view()),
    path('usertemplates/import/',
         UserTemplateImportView.as_view()),
    path('usertemplates/<int:pk>/logo/', UserTemplateLogoView.as_view()),

    # Favorite templates APIs
    path('favorite/',
         FavoriteTemplateListView.as_view()),
    path('favorite/<str:code>/',
         FavoriteTemplateView.as_view()),

    # Template job APIs
    path(
        'templatejob/<int:jobid>/',
        TemplateJobView.as_view()
    ),
    path(
        'internal/templatejob/<int:jobid>/',
        TemplateJobInternalView.as_view()
    ),

    # OpenAPI
    path('openapi/v1/job/submit/', SubmitJobView.as_view()),

    # Notify
    path('notifyjob/', NotifyJobView.as_view()),

    path('alltemplates/', AllTemplatesView.as_view()),
    path('categories/', CategoriesView.as_view()),
    path('templatesdesc/', TemplatesDescView.as_view()),

    # Fixtures
    path('default-run-time/', TemplateDefaultRunTimeView.as_view()),

    # Entrance URL
    path('entrance_url/<int:job_id>/', EntranceURLView.as_view()),
]
