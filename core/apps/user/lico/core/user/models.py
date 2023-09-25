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

from datetime import timedelta

from django.conf import settings
from django.db.models import (
    CASCADE, BooleanField, CharField, EmailField, ForeignKey, IntegerField,
    OneToOneField,
)
from django.utils import timezone

from lico.core.contrib.dataclass import User as UserDataClass
from lico.core.contrib.fields import DateTimeField
from lico.core.contrib.models import Model


class User(Model):
    ADMIN_ROLE = UserDataClass.ADMIN_ROLE
    OPERATOR_ROLE = UserDataClass.OPERATOR_ROLE
    USER_ROLE = UserDataClass.USER_ROLE
    ROLES = {
        ADMIN_ROLE: 'admin',
        OPERATOR_ROLE: 'operator',
        USER_ROLE: 'user'
    }
    ROLE_NAMES = {r[1]: r[0] for r in ROLES.items()}

    username = CharField(
        unique=True, max_length=32, db_index=True
    )
    first_name = CharField(max_length=30, null=True)
    last_name = CharField(max_length=30, null=True)
    email = EmailField(null=True)
    role = IntegerField(
        choices=ROLES.items(),
        default=UserDataClass.USER_ROLE
    )

    date_joined = DateTimeField(auto_now_add=True)

    last_login = DateTimeField(null=True)
    fail_chances = IntegerField(default=0, null=False)
    effective_time = DateTimeField(auto_now_add=True, null=False)

    def login_success(self):
        self.last_login = timezone.now()
        self.fail_chances = 0
        self.save()

    def login_fail(self):
        from datetime import timedelta
        self.fail_chances += 1
        if self.fail_chances >= settings.USER.LOGIN.MAX_CHANCE:
            self.fail_chances = 0
            self.effective_time = \
                timezone.now() + \
                timedelta(hours=settings.USER.LOGIN.LOCKED_HOURS)

        self.save()

    @property
    def remain_chances(self) -> int:
        return settings.USER.LOGIN.MAX_CHANCE - self.fail_chances

    @property
    def remain_time(self) -> timedelta:
        now = timezone.now()
        return timedelta() \
            if now >= self.effective_time \
            else self.effective_time - now

    @property
    def is_activate(self) -> bool:
        return timezone.now() >= self.effective_time

    @property
    def is_admin(self) -> bool:
        return self.role >= self.ADMIN_ROLE

    @property
    def is_operator(self) -> bool:
        return self.role >= self.OPERATOR_ROLE

    @property
    def is_user(self) -> bool:
        return self.role >= self.USER_ROLE

    @property
    def role_name(self) -> str:
        return self.ROLES[self.role]

    @staticmethod
    def get_full_name(first_name, last_name) -> str:
        return f"{first_name} {last_name}".strip()


class ApiKey(Model):
    api_key = CharField(max_length=50, null=True, unique=True)
    create_time = DateTimeField(auto_now_add=True)
    expire_time = DateTimeField(null=True)
    user = OneToOneField(User, null=False, on_delete=CASCADE,
                         related_name="apikey")

    @property
    def is_activate(self) -> bool:
        return False if not self.user.is_activate else \
            self.expire_time is \
            None or timezone.now() <= self.expire_time

    @staticmethod
    def generate_key() -> str:
        from cryptography.fernet import Fernet
        return Fernet.generate_key().decode()

    def save(self, *args, **kwargs):
        if self.api_key is None:
            self.api_key = self.generate_key()
        return super().save(*args, **kwargs)

    def as_dict_on_finished(self, result, is_exlucded, **kwargs):
        if not is_exlucded('status'):
            result['status'] = self.is_activate


class ImportRecordTask(Model):
    is_running = BooleanField(default=True)
    owner = CharField(max_length=32, null=False, unique=True)
    create_time = DateTimeField(auto_now_add=True)
    update_time = DateTimeField(auto_now=True)


class ImportRecord(Model):
    task = ForeignKey(
        ImportRecordTask, null=False,
        on_delete=CASCADE, related_name="records"
    )
    row = IntegerField(null=False)
    username = CharField(max_length=32, null=False)
    role = IntegerField(
        choices=User.ROLES.items(),
        default=User.USER_ROLE
    )
    first_name = CharField(max_length=30, null=True)
    last_name = CharField(max_length=30, null=True)
    email = EmailField(null=True)
    ret = BooleanField(null=True)
    error_message = CharField(max_length=50, null=True)

    class Meta:
        unique_together = ("task", "row", "username")
