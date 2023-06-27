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

from django.urls import path, re_path

from .views.cluster_report_view import (
    DistributionView, OverallView, TimeView, TrendView,
)
from .views.history_job_view import SyncHistoryJobView
from .views.job_comment_view import JobCommentView
from .views.job_history import JobHistoryView, JobHistoryViewUser
from .views.job_latest_view import JobLatestView, JobLatestViewUser
from .views.job_list import JobList
from .views.job_log_view import JobLogView
from .views.job_rerun_view import JobRerunView
from .views.job_resource_view import (
    HostResourceUsedView, RunningJobResourceView, RunningJobsDetailView,
)
from .views.job_statistic import JobHistoryStatisticView, JobStatisticView
from .views.job_submit_view import JobSubmitView
from .views.job_view import (
    InternalJobView, JobListView, JobRawInfoView, JobView,
)
from .views.queue import QueueListView
from .views.recent_job_view import RecentJobListView, UserRecentJobListView
from .views.report_view import JobReportPreview, ReportView
from .views.running_job_view import RunningJobDetailView
from .views.scheduler_view import (
    SchedulerGresTypeView, SchedulerLicenseFeatureView, SchedulerRuntimeView,
    SchedulerStatusView,
)
from .views.tag_view import TagView

urlpatterns = [
    path('', JobListView.as_view()),
    path('<int:pk>/', JobView.as_view()),
    path('log/', JobLogView.as_view()),

    path('latest/user/', JobLatestViewUser.as_view()),
    path('latest/', JobLatestView.as_view()),

    path('queue/', QueueListView.as_view()),
    path('license/', SchedulerLicenseFeatureView.as_view()),

    path('scheduler/status/', SchedulerStatusView.as_view()),
    path('scheduler/runtime/', SchedulerRuntimeView.as_view()),
    path('scheduler/gres/type/', SchedulerGresTypeView.as_view()),

    # to be deprecated
    path('raw_info/<int:pk>/', JobRawInfoView.as_view()),

    # internal view
    path('submit/', JobSubmitView.as_view()),
    path('running_job/resource/', RunningJobResourceView.as_view()),
    path('host_resource_used/', HostResourceUsedView.as_view()),
    path('recent_job/', RecentJobListView.as_view()),
    path('recent_job/user_job/', UserRecentJobListView.as_view()),
    path('sync/history_job/', SyncHistoryJobView.as_view()),
    path('internal/<int:pk>/', InternalJobView.as_view()),
    path('rerun/<int:pk>/', JobRerunView.as_view()),
    path('running/jobs/', RunningJobsDetailView.as_view()),
    path('job_list/', JobList.as_view()),

    # job status chart
    path('job_history/', JobHistoryView.as_view()),
    path('job_history/user/', JobHistoryViewUser.as_view()),

    # job statistic
    path('statistic/', JobStatisticView.as_view()),
    path('job_history/statistic/', JobHistoryStatisticView.as_view()),

    # cluster report
    path('cluster_report/overall/', OverallView.as_view()),
    path('cluster_report/trend/', TrendView.as_view()),
    path('cluster_report/time/', TimeView.as_view()),
    path('cluster_report/distribution/', DistributionView.as_view()),

    path('nodes/<str:hostname>/runningjobs/', RunningJobDetailView.as_view()),
    re_path('(?P<category>user|job|bill_group)/?$',
            JobReportPreview.as_view()),
    path('job_report/<str:filename>/', ReportView.as_view()),

    # openapi
    path('openapi/v1/<int:pk>/', JobView.as_view()),

    path('tag/', TagView.as_view()),
    path('<int:pk>/comment/', JobCommentView.as_view()),
]
