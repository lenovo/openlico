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

from django.core.exceptions import ObjectDoesNotExist
from rest_framework.exceptions import NotFound
from rest_framework.views import exception_handler as old_exception_handler

logger = logging.getLogger(__name__)


def exception_handler(exc, context):
    logger.exception('Error Occured')
    if isinstance(exc, ObjectDoesNotExist):
        exc = NotFound(
            detail=dict(
                message=str(exc),
                type=exc.__class__.__name__
            )
        )
    return old_exception_handler(
        exc, context
    )
