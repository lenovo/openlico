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

import json

from django.core.management import BaseCommand

from lico.core.container.singularity.models import SingularityImage


class Command(BaseCommand):
    help = 'list the names or system image or ' \
           'query a image details by name'

    def add_arguments(self, parser):
        parser.add_argument(
            'name',
            help='query a image details by name',
            nargs='?'
        )

    def handle(self, *args, **options):
        if options["name"] is None:
            for image in SingularityImage.objects.filter(
                    username='').iterator():
                print(image.name)
        else:
            print(
                self._get_image_info(options['name'])
            )

    def _get_image_info(self, name):
        try:
            image = SingularityImage.objects.get(name=name, username='')
        except SingularityImage.DoesNotExist:
            raise SystemExit(
                f'\033[31m{name} image does not exist\033[0m'
            )

        data = image.as_dict()
        return json.dumps(data, indent=4)
