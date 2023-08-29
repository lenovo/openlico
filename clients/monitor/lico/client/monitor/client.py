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

import json
import logging

from lico.client.contrib.client import BaseClient

from .dataclass import Process, ResData

logger = logging.getLogger(__name__)


class Client(BaseClient):
    app = 'monitor'

    def get(self, *args, **kwargs):  # pragma: no cover
        import time

        from requests.exceptions import ConnectionError
        kwargs.setdefault('allow_redirects', True)
        connection_error = None
        for i in range(3):
            try:
                response = self.execute_request('get', *args, **kwargs)
            except ConnectionError as e:
                connection_error = e
                logger.warning(
                    "Access lico-monitor-client api failed. Aleady tried "
                    "{} times".format(i + 1)
                )
                time.sleep(2)
                continue
            except Exception as e:
                raise e
            else:
                return response
        raise ConnectionError from connection_error

    def get_cluster_sockets(self):
        response = self.get(
            self.get_url('socket/'),
        )

        return response["cluster_cpu"], response["cluster_gpu"]

    def get_cluster_resource(self):
        response = self.get(
            self.get_url("internal/resource/cluster/"),
        )
        return [ResData.to_obj(res_dict) for res_dict in response]

    def get_scheduler_resource(self):
        response = self.get(
            self.get_url("internal/resource/scheduler/"),
        )
        return [ResData.to_obj(res_dict) for res_dict in response]

    def get_process_info(self, hostname, pids):
        response = self.get(
            self.get_url("internal/process/{}/".format(hostname)),
            params={'pids': json.dumps(pids)}
        )
        return [
            Process(
                pid=process["pid"],
                user=process["user"]
            )
            for process in response["data"]
        ]
