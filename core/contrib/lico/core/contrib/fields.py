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

import logging

from django.db.models import DateTimeField as BaseDateTimeField
from jsonfield import JSONCharField, JSONField

logger = logging.getLogger(__name__)

__all__ = ['JSONField', 'JSONCharField', 'DateTimeField']


class DateTimeField(BaseDateTimeField):
    def dict_from_object(self, obj):
        value = self.value_from_object(obj)
        return int(value.timestamp()) if value is not None else None
