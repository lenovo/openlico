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

from django.conf import settings
from django.core.management import BaseCommand

from lico.core.cluster.utils import clean, config, sync


class Command(BaseCommand):
    help = 'sync node from nodes.csv'

    def add_arguments(self, parser):
        if settings.CLUSTER.SYNC_NODES_WITH_CONFLUENT:
            parser.add_argument(
                '--not-sync-with-confluent',
                action='store_true',
                default=False,
                help='Sync nodes info with confluent'
            )
        else:
            parser.add_argument(
                '--sync-with-confluent',
                action='store_true',
                default=False,
                help='Sync nodes info with confluent'
            )

    def handle(self, *args, **options):
        logging.basicConfig(level=logging.INFO)

        conf = config.Configure.parse(
            settings.CLUSTER.NODES_FILE
        )
        for group in conf.group:
            if group.name.lower() == 'all':
                message = \
                    "The name 'all' is the system group name, " \
                    "please don't use it."
                raise Exception(message)
        sync.sync2db(configure=conf)

        sync_with_confuent = not options['not_sync_with_confluent'] \
            if settings.CLUSTER.SYNC_NODES_WITH_CONFLUENT else \
            options['sync_with_confluent']

        if sync_with_confuent:
            sync.sync2confluent(configure=conf)
            clean.cleanNodesSensitiveContent(
                configure_file=settings.CLUSTER.NODES_FILE
            )
