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

from django.urls import path

from .views import HostlistExpandView, HostlistFoldView, NodeEditorFixturesView
from .views.group import (
    NodeGroupHostList, NodeGroupInternalAddView, NodegroupInternalDetailView,
    NodeGroupView,
)
from .views.node import (
    NodeAllView, NodeDetailView, NodeHostList, NodeInternalAddView,
    NodeInternalDetailView, NodeListView,
)
from .views.rack import (
    RackDetailView, RackHierarchyView, RackHostList, RackInternalAddView,
    RackInternalDetailView, RackView,
)
from .views.room import RoomInternalAddView, RoomInternalDetailView, RoomView
from .views.row import (
    RowDetailView, RowInternalAddView, RowInternalDetailView, RowRacksList,
    RowsView,
)

urlpatterns = [
    path('node/', NodeListView.as_view()),
    path('node/all/', NodeAllView.as_view()),
    path('node/host/list/', NodeHostList.as_view()),  # internal
    path('node/<str:hostname>/', NodeDetailView.as_view()),
    path('node/internal/add/', NodeInternalAddView.as_view()),  # internal
    path(
        'node/internal/<str:hostname>/detail/',
        NodeInternalDetailView.as_view()
    ),  # internal
    path('room/', RoomView.as_view()),
    path('room/internal/add/', RoomInternalAddView.as_view()),  # internal
    path(
        'room/internal/<str:name>/detail/', RoomInternalDetailView.as_view()
    ),  # internal
    path('row/', RowsView.as_view()),
    path('row/<str:name>/', RowDetailView.as_view()),
    path('row/rack/list/', RowRacksList.as_view()),  # internal
    path('row/internal/add/', RowInternalAddView.as_view()),  # internal
    path(
        'row/internal/<str:name>/detail/', RowInternalDetailView.as_view()
    ),  # internal
    path('rack/', RackView.as_view()),
    path('rack/<str:name>/', RackDetailView.as_view()),
    path('rack/host/list/', RackHostList.as_view()),  # internal
    path('rack/internal/add/', RackInternalAddView.as_view()),  # internal
    path(
        'rack/internal/<str:name>/detail/', RackInternalDetailView.as_view()
    ),  # internal
    path('nodegroup/', NodeGroupView.as_view()),
    path('nodegroup/host/list/', NodeGroupHostList.as_view()),  # internal
    path(
        'nodegroup/internal/add/',
        NodeGroupInternalAddView.as_view()
    ),  # internal
    path(
        'nodegroup/internal/<str:name>/detail/',
        NodegroupInternalDetailView.as_view()
    ),  # internal
    path('rack_hierarchy/', RackHierarchyView.as_view()),
    path('node-editor-fixtures/', NodeEditorFixturesView.as_view()),
    path('hostlist/fold/', HostlistFoldView.as_view()),
    path('hostlist/expand/', HostlistExpandView.as_view()),
]
