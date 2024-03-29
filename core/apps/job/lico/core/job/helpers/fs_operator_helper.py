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


def get_fs_operator(user):
    from lico.core.contrib.client import Client
    return Client().filesystem_client(user=user)


def get_fs_operator_by_username(username):
    from lico.core.contrib.client import Client
    auth_client = Client().auth_client()
    user = auth_client.get_user_info(username)
    return Client().filesystem_client(user=user)
