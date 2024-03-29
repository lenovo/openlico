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

from django.db.backends.mysql import base

from .client import DatabaseClient


class DatabaseWrapper(base.DatabaseWrapper):
    client_class = DatabaseClient

    def ensure_connection(self):
        if self.connection:
            if self.autocommit:
                self.connection.ping(True)

        super().ensure_connection()
