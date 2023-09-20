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

import logging

logger = logging.getLogger(__name__)


def app_factory(
        global_config,
        configure='/var/lib/lico/mail-agent.json',
        timeout=60,
        **local_conf
):
    import falcon

    from .resource import Configure, Message

    app = falcon.API()
    app.req_options.strip_url_path_trailing_slash = True
    app.add_route(
        '/api/notice/mail/config', Configure(configure)
    )
    app.add_route(
        '/api/notice/mail', Message(
            configure,
            timeout=timeout
        )
    )

    return app
