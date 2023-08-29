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


from django.core.management import BaseCommand
from django.db.transaction import atomic
from py.path import local

from lico.core.container.singularity.models import SingularityImage


class Command(BaseCommand):
    help = 'delete system image.'

    def add_arguments(self, parser):
        parser.add_argument('name', help='image name to delete')

    @atomic()
    def handle(self, *args, **options):
        image_name = options['name']
        try:
            image_obj = SingularityImage.objects.get(
                    username='', name=image_name
                )
        except SingularityImage.DoesNotExist:
            raise SystemExit(f'Image {image_name} not exists.')

        image_path = local(image_obj.image_path)
        if image_path.exists():
            image_path.remove()
        image_obj.delete()
        print(f'Delete image {image_name} success.')
