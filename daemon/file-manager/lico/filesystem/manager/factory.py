# -*- coding: utf-8 -*-
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

from .adapter import HostAdapter
from .resource import FileManager


def create_app(global_config, upload_max_size='5'):
    import falcon
    import simplejson
    from falcon_multipart.middleware import MultipartMiddleware

    json_handler = falcon.media.JSONHandler(
        loads=simplejson.loads,
        dumps=simplejson.dumps
    )

    api = falcon.API(middleware=[MultipartMiddleware()])

    api.req_options.strip_url_path_trailing_slash = True
    api.req_options.auto_parse_form_urlencoded = True
    api.resp_options.media_handlers.update({
        'application/json': json_handler,
    })

    adapter = HostAdapter()
    api.add_route('/api/file', FileManager(adapter, upload_max_size))

    return api
