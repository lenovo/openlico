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

logger = logging.getLogger(__name__)


def get_fs_operator():
    return HostFileManger()


class HostFileManger:
    def __init__(self):
        from lico.client.filesystem.local import LocalFileSystem
        self.filesystem = LocalFileSystem()

    def upload_file(self, local_path, remote_path):
        self.filesystem.copyfile(local_path, remote_path)
