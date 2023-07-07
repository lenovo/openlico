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

from typing import Callable, Dict

from django.db.models import (
    PROTECT, BooleanField, CharField, ForeignKey, IntegerField,
    ManyToManyField, TextField,
)

from lico.core.contrib.client import Client
from lico.core.contrib.fields import DateTimeField
from lico.core.contrib.models import Model
from lico.core.job.helpers.fs_operator_helper import get_fs_operator


class Tag(Model):
    name = CharField(max_length=24, null=False)
    username = CharField(max_length=32, null=False)
    count = IntegerField(null=False, blank=True, default=0)
    create_time = DateTimeField(auto_now_add=True)
    update_time = DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("name", "username")
        ordering = ["jobtags__create_time"]


class Job(Model):
    scheduler_id = CharField(null=False, max_length=64, blank=True,
                             default="", db_index=True)
    identity_str = CharField(null=False, max_length=128, blank=True,
                             default="", db_index=True)
    job_name = CharField(null=False, max_length=128, blank=True, default="")
    job_content = TextField(null=False, blank=True, default="")
    queue = CharField(null=False, max_length=128, blank=True, default="")
    submit_time = DateTimeField(auto_now_add=True)
    start_time = DateTimeField(null=True, blank=True)
    end_time = DateTimeField(null=True, blank=True)
    submitter = CharField(null=False, max_length=32, blank=True, default="")
    job_file = CharField(null=False, max_length=260, blank=True, default="")
    workspace = CharField(null=False, max_length=260, blank=True, default="")
    scheduler_state = CharField(null=False, max_length=24, blank=True,
                                default="")
    state = CharField(null=False, max_length=24, blank=True, default="")
    operate_state = CharField(null=False, max_length=24, blank=True,
                              default="")
    delete_flag = BooleanField(null=False, blank=True, default=False)
    runtime = IntegerField(null=False, blank=True, default=0)
    standard_output_file = CharField(null=False, max_length=260, blank=True,
                                     default="")
    error_output_file = CharField(null=False, max_length=260, blank=True,
                                  default="")
    raw_info = TextField(null=False, blank=True, default="")
    reason = TextField(null=False, blank=True, default="")
    comment = CharField(null=False, max_length=256, blank=True, default="")
    exit_code = CharField(null=False, max_length=16, blank=True, default="")
    tres = TextField(null=False, blank=True, default="")
    create_time = DateTimeField(auto_now_add=True)
    update_time = DateTimeField(auto_now=True)
    tags = ManyToManyField(Tag, through="JobTags")
    user_comment = TextField(null=True, blank=True, default="")
    priority = CharField(null=True, max_length=16, blank=True, default="")

    @property
    def get_job_password(self):
        import re
        search_obj = re.search(
            r"PASSWORD='([^\n]*)'",
            self.job_content
        )
        if search_obj:
            return search_obj.group(1)
        return None

    @property
    def get_entrance_uri(self):
        entrance_uri_path = \
            f"{self.workspace}/{self.scheduler_id}_entrance_uri.txt"

        client = Client().auth_client()
        user = client.get_user_info(self.submitter)
        fopr = get_fs_operator(user)

        if fopr.path_exists(entrance_uri_path):
            with fopr.open_file(entrance_uri_path, 'r') as f:
                entrance_uri = f.file_handle.read().strip()
                if entrance_uri:
                    return entrance_uri
        return None

    def as_dict_on_finished(
            self, result: Dict, is_exlucded: Callable, **kwargs
    ):
        for k, v in kwargs.get("on_finished_options", {}).items():
            if not is_exlucded(k) and hasattr(self, v):
                result[k] = getattr(self, v)


class JobTags(Model):
    job = ForeignKey("Job", on_delete=PROTECT)
    tag = ForeignKey("Tag", on_delete=PROTECT)
    create_time = DateTimeField(auto_now_add=True)
    update_time = DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("job", "tag")


class JobRunning(Model):
    job = ForeignKey(Job, blank=False, on_delete=PROTECT,
                     related_name='job_running')
    hosts = TextField(null=False, blank=True, default="")
    per_host_tres = TextField(null=False, blank=True, default="")
    allocate_time = DateTimeField(null=True, blank=True)


class JobCSRES(Model):
    job = ForeignKey(Job, blank=False, on_delete=PROTECT,
                     related_name='job_csres')
    csres_code = CharField(null=False, max_length=16, blank=True, default="")
    csres_value = CharField(null=False, max_length=16, blank=True, default="")
