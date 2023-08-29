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

from functools import partial

from lico.password import fetch_pass


def get_influxdb_client(settings):  # pragma: no cover
    from influxdb.client import InfluxDBClient
    kwargs = {
        key.lower(): value
        for key, value in settings.INFLUXDB.items()
    }
    kwargs.setdefault('host', '127.0.0.1')
    kwargs.setdefault('database', '_internal')

    user, password = fetch_pass('influxdb')
    if user is not None and password is not None:
        kwargs.setdefault('username', user)
        kwargs.setdefault('password', password)

    return partial(InfluxDBClient, **kwargs)


def get_influxdb_dataframe_client(settings):  # pragma: no cover
    from influxdb.dataframe_client import DataFrameClient
    kwargs = {
        key.lower(): value
        for key, value in settings.INFLUXDB.items()
    }
    kwargs.setdefault('host', '127.0.0.1')
    kwargs.setdefault('database', '_internal')

    user, password = fetch_pass('influxdb')
    if user is not None and password is not None:
        kwargs.setdefault('username', user)
        kwargs.setdefault('password', password)

    return partial(DataFrameClient, **kwargs)
