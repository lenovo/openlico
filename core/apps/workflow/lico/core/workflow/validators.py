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

from celery.schedules import crontab
from django.core.exceptions import ValidationError


def minute_validator(value):
    """Validate minutes crontab value."""
    _validate_crontab(value, 60)


def hour_validator(value):
    """Validate hours crontab value."""
    _validate_crontab(value, 24)


def day_of_month_validator(value):
    """Validate day of month crontab value."""
    _validate_crontab(value, 31, 1)


def month_of_year_validator(value):
    """Validate month crontab value."""
    _validate_crontab(value, 12, 1)


def day_of_week_validator(value):
    """Validate day of week crontab value."""
    _validate_crontab(value, 7)


def _validate_crontab(value, max_, min_=0):
    try:
        crontab._expand_cronspec(value, max_, min_)
    except ValueError as e:
        raise ValidationError(e)
