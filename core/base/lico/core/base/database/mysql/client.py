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

import subprocess  # nosec B404
import sys

from django.db.backends.mysql import client


class DatabaseClient(client.DatabaseClient):
    def runshell(self):
        args = DatabaseClient.settings_to_cmd_args(
            self.connection.settings_dict
        )
        sys.exit(
            subprocess.call(args)  # nosec B603
        )
