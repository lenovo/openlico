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

import tomli


class Database:

    def __init__(self, db):
        self.db = db

    def read_db(self, keyword: str):
        toml_dict = tomli.load(self.db)
        if keyword in toml_dict:
            username = toml_dict[keyword].get('username')
            if username == '':
                username = None
            password = toml_dict[keyword].get('password')
            if password == '':  # nosec B105
                password = None
            return username, password
        return None, None

    def get(self, keyword: str):
        return self.read_db(
            keyword=keyword
        )
