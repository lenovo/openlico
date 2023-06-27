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

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def startup_device(node, bootmode, nextdevice, persistent):
    logger.debug(
        'Start up device %s through confluent %s',
        node.hostname,
    )
    if nextdevice:
        set_nextdevice_bootmode(node, bootmode, nextdevice, persistent)

    _startup_device(node)


def shutdown_device(node):
    logger.debug(
        'Shutdown device %s through confluent %s',
        node.hostname, settings.CLUSTER.CONFLUENT.HOST
    )

    url = 'http://{}:{}/nodes/{}/power/state'.format(
        settings.CLUSTER.CONFLUENT.HOST,
        settings.CLUSTER.CONFLUENT.PORT,
        node.hostname
    )

    res = requests.put(
        url,
        auth=(
            settings.CLUSTER.CONFLUENT.USER,
            settings.CLUSTER.CONFLUENT.PASS
        ),
        headers={
            'accept': 'application/json'
        },
        json={'state': 'off'},
        timeout=settings.CLUSTER.CONFLUENT.REQUESTS_TIMEOUT
    )
    res.raise_for_status()


def _startup_device(node):
    url = 'http://{}:{}/nodes/{}/power/state'.format(
        settings.CLUSTER.CONFLUENT.HOST,
        settings.CLUSTER.CONFLUENT.PORT,
        node.hostname
    )

    res = requests.post(
        url,
        auth=(
            settings.CLUSTER.CONFLUENT.USER,
            settings.CLUSTER.CONFLUENT.PASS
        ),
        headers={
            'accept': 'application/json'
        },
        json={'state': 'boot'},
        timeout=settings.CLUSTER.CONFLUENT.REQUESTS_TIMEOUT
    )
    res.raise_for_status()


def set_nextdevice_bootmode(node, bootmode, nextdevice, persistent):
    url = 'http://{}:{}/nodes/{}/boot/nextdevice'.format(
        settings.CLUSTER.CONFLUENT.HOST,
        settings.CLUSTER.CONFLUENT.PORT,
        node.hostname
    )
    res = requests.post(
        url,
        auth=(
            settings.CLUSTER.CONFLUENT.USER,
            settings.CLUSTER.CONFLUENT.PASS
        ),
        headers={
            'accept': 'application/json'
        },
        json={
            'bootmode': bootmode,
            'nextdevice': nextdevice,
            'persistent': persistent
        },
        timeout=settings.CLUSTER.CONFLUENT.REQUESTS_TIMEOUT
    )
    res.raise_for_status()
