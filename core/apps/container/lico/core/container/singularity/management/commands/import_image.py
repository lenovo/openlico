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


import pwd
import stat

from django.conf import settings
from django.core.management import BaseCommand
from django.db.transaction import atomic
from py.path import local

from lico.core.container.singularity.models import (
    SingularityImage, SingularityImageTag,
)
from lico.core.container.singularity.utils import TaskStatus


class Command(BaseCommand):
    help = 'import system image.'

    def add_arguments(self, parser):
        parser.add_argument('name', help='image name')
        parser.add_argument('image_path', help='image path')
        parser.add_argument(
            'framework', help='framework type',
            choices=settings.CONTAINER.IMAGE_FRAMEWORKS
        )
        parser.add_argument(
            '-V', '--ver', help='framework version'
        )
        parser.add_argument(
            '-t', '--tag', help='tags for image, separated by commas',
            default=[],
            action='append'
        )
        parser.add_argument(
            '-d', '--description', help='image description'
        )

    @atomic
    def handle(self, *args, **options):
        image_store_dir = local(settings.CONTAINER.AI_CONTAINER_ROOT).\
            ensure(dir=True)
        image_store_path = image_store_dir.join(f"{options['name']}.image")

        source_image_path = local(options['image_path'])
        source_image_filename = source_image_path.basename

        if not source_image_path.exists():
            print(f'{source_image_path} does not exists.')
            raise SystemExit(-1)

        # copy image file
        source_image_path.copy(image_store_path)
        print(
            f'{source_image_filename} has been copied to {image_store_dir}'
        )

        # set owner and permission
        uid = pwd.getpwnam('root').pw_uid
        gid = pwd.getpwnam('root').pw_gid

        image_store_path.chown(uid, gid)
        image_store_path.chmod(
            stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH
        )

        # insert into database
        image, _ = SingularityImage.objects.update_or_create(
            name=options['name'],
            username='',
            defaults={
                "framework": options['framework'],
                "image_path": str(image_store_path),
                "description": options['description'],
                "version": options['ver'],
                'status': TaskStatus.SUCCESS.value
            }
        )
        image.tags.all().delete()

        SingularityImageTag.objects.bulk_create([
            SingularityImageTag(
                image=image,
                index=index,
                name=item,
            )
            for index, item in enumerate(options['tag'])
        ])

        print('Import image success.')
