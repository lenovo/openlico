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

from falcon.errors import HTTPBadRequest


class MaxJobsReached(HTTPBadRequest):
    def __init__(self):
        super().__init__(
            code=9007,
            description='Max Jobs Reached.'
        )


class EmptyBuilders(Exception):
    pass


class INITERROR(HTTPBadRequest):
    def __init__(self):
        super().__init__(
            code=9015,
            description='Task init error.'
        )


class RUNERROR(HTTPBadRequest):
    def __init__(self):
        super().__init__(
            code=9016,
            description='Task run error.'
        )


class OUTPUTERROR(HTTPBadRequest):
    def __init__(self):
        super().__init__(
            code=9017,
            description='Task output error.'
        )
