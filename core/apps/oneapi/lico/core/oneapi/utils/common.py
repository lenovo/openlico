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

import hashlib


def make_hash(to_hash: str) -> str:
    """Return a hash of to_hash."""
    hash_obj = hashlib.md5()  # nosec B303
    hash_obj.update(to_hash.encode("utf-8"))
    hash_code = str(hash_obj.hexdigest())
    return hash_code
