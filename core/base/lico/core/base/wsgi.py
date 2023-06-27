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

import django
from django.conf import settings
from django.core.handlers.wsgi import WSGIHandler

from .main import set_env

set_env()


class LiCOWSGIHandler(WSGIHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        from .subapp import iter_sub_apps
        for app in iter_sub_apps():
            app.on_wsgi_init(settings)


def get_lico_wsgi_application():
    django.setup(set_prefix=False)
    return LiCOWSGIHandler()


application = get_lico_wsgi_application()


def make_application(global_config, **local_conf):
    return application
