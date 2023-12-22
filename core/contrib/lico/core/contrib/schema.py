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

from jsonschema import ValidationError, validate

from .exceptions import InvalidJSON

logger = logging.getLogger(__name__)


def json_schema_validate(schema, is_get=False):
    def validate_func(func):
        def _func(self, request, *args, **kwargs):
            try:
                if not is_get:
                    validate(request.data, schema)
                else:
                    validate(request.query_params, schema)
            except ValidationError as e:
                logger.exception('Invalid jsonschema')
                raise InvalidJSON(e) from e
            else:
                return func(self, request, *args, **kwargs)
        return _func
    return validate_func
