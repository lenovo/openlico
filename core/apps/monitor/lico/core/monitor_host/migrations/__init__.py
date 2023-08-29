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

from django.db.migrations.operations.base import Operation


class CreatePreferenceData(Operation):  # pragma: no cover
    reversible = True

    def __init__(self, name, value):
        from datetime import datetime
        self.name = name
        self.value = value
        self.create_time = datetime.now()
        self.modify_time = self.create_time

    def state_forwards(self, app_label, state):
        pass

    def database_forwards(self, app_label, schema_editor,
                          from_state, to_state):
        schema_editor.execute(
            "INSERT INTO monitor_host_preference "
            "(NAME,VALUE,CREATE_TIME,MODIFY_TIME) VALUES "
            "(%s,%s,%s,%s);",
            params=(
                self.name, self.value, self.create_time, self.modify_time
            )
        )

    def database_backwards(self, app_label, schema_editor,
                           from_state, to_state):
        schema_editor.execute('DROP TABLE monitor_host_preference;')

    def describe(self):
        return "Creates  a Preference data: name is {}, value is {}." \
            .format(self.name, self.value)
