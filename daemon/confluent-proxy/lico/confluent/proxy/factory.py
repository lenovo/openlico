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


def _build_app():
    import falcon

    app = falcon.API()

    return app


def _add_route(app, client):
    from .resource import Async, Console, Shell

    app.req_options.strip_url_path_trailing_slash = True

    app.add_route('/api/confluent/async', Async(client))
    app.add_route('/api/confluent/shell/{name}', Shell(client))
    app.add_route('/api/confluent/console/{name}', Console(client))


def app_factory(  # nosec B107
        global_conf,
        host='127.0.0.1',
        port='4005',
        user='',
        password='',
        timeout=180,
        members='',
        db_host='127.0.0.1',
        db_database='lico',
        db_port=3306
):
    app = _build_app()

    from lico.password import fetch_pass
    saved_user, saved_password = fetch_pass('confluent')
    if saved_user is not None and saved_password is not None:
        user, password = saved_user, saved_password

    from .client import ClusterConfluentClient, ConfluentClient
    if members:
        members = members.replace(' ', '').split(",")
        db_user, db_pass = fetch_pass('mariadb')
        client = ClusterConfluentClient(
            host=host,
            port=int(port),
            user=user,
            password=password,
            timeout=int(timeout),
            members=members,
            db_host=db_host,
            db_port=db_port,
            db_database=db_database,
            db_user=db_user,
            db_pass=db_pass
        )
    else:
        client = ConfluentClient(
            host=host,
            port=int(port),
            user=user,
            password=password,
            timeout=int(timeout)
        )
    _add_route(app, client)

    return app
