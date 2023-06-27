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

from lico.core.accounting.views.consumeview import (
    ConsumeRankingView, CostStatisticView,
)
from lico.core.contrib.authentication import RemoteJWTWebAuthentication
from lico.core.contrib.permissions import AsAdminRole

from .views.billgroup import BillGroupDetailView, BillGroupListView
from .views.billingreport import BillingDate, BillingDownload
from .views.chargejob import ChargeJobView
from .views.deposit import (
    DepositDetailView, DepositListDetailView, DepositListView,
    DepositReportView,
)
from .views.discount import DiscountDetailView, DiscountView
from .views.gresource import InternalGreSourceView
from .views.queuepolicy import QueuePolicyDetailView, QueuePolicyView
from .views.storagepolicy import StoragePolicy, StoragePolicyDetailView
from .views.user_billgroup import (
    BillGroupUserListView, InternalBillGroupListView,
    InternalUserBillGroupView, UserBillGroupView,
)

urlpatterns = [
    path('discount/', DiscountView.as_view()),
    path('discount/<int:pk>/', DiscountDetailView.as_view()),
    path('billgroup/', BillGroupListView.as_view()),
    path('billgroup/<int:pk>/', BillGroupDetailView.as_view()),
    path(
        'billgroup/user_list/',
        BillGroupUserListView.as_view(
            authentication_classes=(RemoteJWTWebAuthentication, ),
            permission_classes=(AsAdminRole, ))),
    path('deposit/', DepositListView.as_view()),
    path('deposit_report/<str:filename>/', DepositReportView.as_view()),
    path('deposit/<int:pk>/', DepositDetailView.as_view()),
    path('deposit/list/<str:language>/<int:bill_group_id>/',
         DepositListDetailView.as_view()),
    path('queuepolicy/<int:pk>/', QueuePolicyView.as_view()),
    path('queuepolicy/<int:pk>/<int:policy_pk>/',
         QueuePolicyDetailView.as_view()),
    path('storagepolicy/<int:pk>/', StoragePolicy.as_view()),
    path('storagepolicy/<int:pk>/<int:storage_pk>/',
         StoragePolicyDetailView.as_view()),
    path('user_billgroup/', UserBillGroupView.as_view()),
    path('internal/user_billgroup/', InternalUserBillGroupView.as_view()),
    path('internal/billgroup/user_list/', BillGroupUserListView.as_view()),
    path('internal/billgroup/', InternalBillGroupListView.as_view()),
    path('internal/gresource/', InternalGreSourceView.as_view()),
    path('charge/job/', ChargeJobView.as_view()),  # internal
    path('billing/download/', BillingDownload.as_view()),
    path('billing/latestdate/', BillingDate.as_view()),

    # consume report preview api
    path('consume/cost/', CostStatisticView.as_view()),
    path('consume/ranking/', ConsumeRankingView.as_view()),
]
