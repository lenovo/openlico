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

from django.db.models import BooleanField, CharField, IntegerField, TextField

from lico.core.contrib.fields import DateTimeField
from lico.core.contrib.models import Model

logger = logging.getLogger(__name__)


class JobComp(Model):
    STARTED = 'start'
    COMPLETED = 'complete'
    REST = u'rest'
    EMAIL = u'email'
    LICO_REST = 'lico_restapi'
    NOTICE_CHOICES = (
        (REST, u'restapi'),
        (EMAIL, u'email'),
        (LICO_REST, u'lico_restapi')
    )
    job = IntegerField(null=False)
    url = TextField(null=True)
    type = CharField(max_length=20, null=False)
    triggered = BooleanField(default=False)
    method = CharField(
        max_length=20, null=False, default='POST'
    )
    notice_type = CharField(
        max_length=20, choices=NOTICE_CHOICES, default='rest'
    )
    create_time = DateTimeField(auto_now_add=True)
