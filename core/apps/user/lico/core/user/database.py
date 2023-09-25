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

import logging

from django.db import IntegrityError
from django.db.transaction import atomic

from .models import User

try:
    from functools import singledispatchmethod
except ImportError:
    from singledispatchmethod import singledispatchmethod


logger = logging.getLogger(__name__)


class DataBase:
    def add_user(
            self, username, role=User.USER_ROLE, email=None,
            first_name=None, last_name=None
    ):
        try:
            return User.objects.create(
                username=username,
                role=role,
                email=email,
                first_name=first_name,
                last_name=last_name
            )
        except IntegrityError:
            logger.exception("User has already exist")
            raise

    @singledispatchmethod
    def get_user(self, data, lock=False):
        raise NotImplementedError  # pragma: no cover

    @get_user.register(int)
    def _(self, pk, lock=False):
        try:
            query = User.objects
            if lock:
                query = query.select_for_update()
            return query.get(id=pk)
        except User.DoesNotExist:
            logger.exception('The user %s is not exist', pk)
            raise

    @get_user.register(str)
    def _(self, username, lock=False):
        try:
            query = User.objects
            if lock:
                query = query.select_for_update()
            return query.get(username=username)
        except User.DoesNotExist:
            logger.exception('The user %s is not exist', username)
            raise

    @atomic
    def update_user(self, pk, data):
        user = self.get_user(pk, lock=True)
        for k, v in data.items():
            setattr(user, k, v)
        user.save()
        return user

    def is_last_admin(self, pk):
        user = self.get_user(pk)
        return user.role == User.ADMIN_ROLE and User.objects.filter(
            role=User.ADMIN_ROLE
        ).count() == 1
