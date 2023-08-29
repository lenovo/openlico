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

from django.conf import settings

from ..csres.csres_render import CSResRender
from ..csres.port_allocator import PortAllocator


def get_csres_render():
    render = CSResRender(lock_file_directory=settings.JOB.CSRES.LOCK_FILE_DIR)
    port_allocator = PortAllocator(
        settings.JOB.CSRES.PORT_BEGIN,
        settings.JOB.CSRES.PORT_END
    )
    render.append_csres_allocator(port_allocator)
    return render
