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
from functools import lru_cache

import falcon
from pytz import utc

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def manager_factory(max_jobs, builder, port, username, password):
    from apscheduler.schedulers.background import BackgroundScheduler

    from .manager import BuildJobManager

    scheduler = BackgroundScheduler()
    scheduler.configure(
        executors={
            'default': {'type': 'threadpool', 'max_workers': max_jobs}
        },
        job_defaults={
            'coalesce': False,
            'max_instances': 1
        },
        timezone=utc
    )
    manager = BuildJobManager(
        scheduler=scheduler, max_jobs=max_jobs, builder=builder,
        username=username, password=password, port=port
    )
    scheduler.start()

    return manager


def proxy_app_factory(
        global_config, max_jobs: str = '10', async_agent: str = 'localhost',
        workspace: str = '', port: str = '22', username: str = None,
        password: str = None, **local_conf
):
    if not async_agent:
        from .exception import EmptyBuilders
        raise EmptyBuilders

    username = username if username else None
    password = password if password else None

    manager = manager_factory(
        int(max_jobs), async_agent,
        int(port), username, password
    )

    app = falcon.API()
    app.req_options.strip_url_path_trailing_slash = True

    from .resource import BuildJob, BuildJobDetail, FakeBuildJobDetail
    app.add_route(
        '/api/builder/container',
        BuildJob(
            builder=async_agent, manager=manager, namespace=workspace
        )
    )
    app.add_route(
        '/api/builder/container/{host}', FakeBuildJobDetail()
    )
    app.add_route(
        '/api/builder/container/{host}/{id}', BuildJobDetail(manager=manager)
    )

    return app
