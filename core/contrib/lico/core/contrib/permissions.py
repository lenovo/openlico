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

from abc import abstractmethod

from django.contrib.auth.models import AnonymousUser
from rest_framework import permissions

from .dataclass import User


class BaseRole(permissions.BasePermission):
    def __new__(cls, func=None):
        if func:
            func.permission_class = cls
            return func
        else:
            return permissions.BasePermission.__new__(cls)

    @property
    @abstractmethod
    def floor(self):
        pass

    def has_permission(self, request, view):
        if not getattr(request, 'user', None):
            return False

        if isinstance(request.user, AnonymousUser):
            return False

        # if defined method permission
        method = getattr(view, request.method.lower(), None)
        if method is None:
            return False

        method_permission = getattr(method, 'permission_class', None)
        if method_permission:
            return request.user.role >= method_permission.floor

        return request.user.role >= self.floor


class AsUserRole(BaseRole):
    floor = User.USER_ROLE


class AsOperatorRole(BaseRole):
    floor = User.OPERATOR_ROLE


class AsAdminRole(BaseRole):
    floor = User.ADMIN_ROLE


class IsAuthenticated(permissions.BasePermission):
    def has_permission(self, request, view):
        return not isinstance(request.user, AnonymousUser)


class IsAnonymousUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return isinstance(request.user, AnonymousUser)


class SchedulerPermission(permissions.BasePermission):
    message = 'Scheduler permission failed.'

    def has_permission(self, request, view):
        """
        Return `True` if permission is granted, `False` otherwise.
        """
        from django.conf import settings
        if not settings.LICO.get('SCHEDULER', ''):
            return False
        return True
