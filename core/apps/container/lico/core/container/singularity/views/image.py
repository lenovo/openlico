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
from abc import ABCMeta, abstractmethod

from django.conf import settings
from django.db.models import Q
from django.db.transaction import atomic
from django.db.utils import IntegrityError
from py.path import local
from rest_framework.response import Response

from lico.core.container.singularity.utils import (
    check_original_path, user_image_path,
)
from lico.core.contrib.permissions import AsAdminRole
from lico.core.contrib.schema import json_schema_validate
from lico.core.contrib.views import APIView

from ...exceptions import (
    ImageAlreadyExist, ImageNotReady, TargetFileAlreadyExist,
)
from ...views import SearchImageListView
from ..models import SingularityImage, SingularityImageTag
from ..utils import TaskStatus

logger = logging.getLogger(__name__)


class AbstractImageListView(APIView, metaclass=ABCMeta):
    @classmethod
    @abstractmethod
    def _image_query(cls, user):
        return SingularityImage.objects

    @json_schema_validate({
        "type": "object",
        "properties": {
            "framework": {
                "type": "string",
                "minLength": 1
            },
            "tags": {
                "type": "string",
                "minLength": 1
            }
        }
    }, is_get=True)
    def get(self, request):
        framework = request.query_params.get("framework", [])
        tags = request.query_params.get("tags", [])

        images = self._image_query(request.user)
        if framework:
            images = images.filter(
                framework__in=json.loads(framework)
            )
        if tags:
            for tag in json.loads(tags):
                images = images.filter(tags__name=tag)

        return Response(
            dict(data=images.as_dict(exclude=['create_time']))
        )


class ImageListView(AbstractImageListView):
    # query or create image by user
    @classmethod
    def _image_query(cls, user):
        return super()._image_query(user).filter(
            Q(username=user.username) | Q(username='')
        )

    @json_schema_validate({
        'type': 'object',
        'properties': {
            'name': {
                'type': 'string',
                'minLength': 1,
                'maxLength': 100
            },
            'target': {
                'type': 'string',
                'minLength': 1
            },
            'description': {
                'type': 'string',
                'minLength': 1,
            },
            'version': {
                'type': 'string',
                'minLength': 1,
                'maxLength': 32
            },
            'tags': {
                'type': 'array',
                'items': {
                    "type": "string",
                    "minLength": 1
                },

            },
            'file_path': {
                'type': 'string',
                'minLength': 1,
            },
            'framework': {
                'type': 'string',
                'enum': settings.CONTAINER.IMAGE_FRAMEWORKS
            },
        },
        'required': ['name', 'framework', 'file_path', 'target']
    })
    def post(self, request):
        image_path = user_image_path(request.user.workspace).join(
            request.data['target'])

        file_path = local(request.user.workspace).join(
            request.data['file_path'])

        check_original_path(file_path)

        self._create(
            name=request.data['name'],
            image_path=str(image_path),
            username=request.user.username,
            framework=request.data['framework'],
            description=request.data.get('description'),
            version=request.data.get('version'),
            tags=request.data.get('tags', []),
            file_path=str(file_path)
        )
        return Response()

    def _create(self, name, image_path, username, framework, description,
                version, tags, file_path):
        with atomic():
            try:
                image = SingularityImage.objects.create(
                    name=name,
                    image_path=image_path,
                    username=username,
                    framework=framework,
                    description=description,
                    version=version
                )

            except IntegrityError as e:
                logger.exception('Image has already exist')
                raise ImageAlreadyExist from e

            SingularityImageTag.objects.bulk_create([
                SingularityImageTag(image=image, index=index, name=name)
                for index, name in enumerate(tags)
            ])

        from ..tasks import copy_image
        copy_image.delay(image.id, file_path)


class SystemImageListView(AbstractImageListView):
    # query or create image by admin
    permission_classes = (AsAdminRole,)

    @classmethod
    def _image_query(cls, user):
        return super()._image_query(user).filter(username='')

    @json_schema_validate({
        'type': 'object',
        'properties': {
            'name': {
                'type': 'string',
                'minLength': 1,
                'maxLength': 100
            },
            'target': {
                'type': 'string',
                'minLength': 1
            },
            'description': {
                'type': 'string',
                'minLength': 1,
            },
            'version': {
                'type': 'string',
                'minLength': 1,
                'maxLength': 32
            },
            'tags':  {
                "type": "array",
                'items': {
                    "type": "string"
                },
            },
            'file_path': {
                'type': 'string',
                'minLength': 1,
            },
            'framework': {
                'type': 'string',
                'enum': settings.CONTAINER.IMAGE_FRAMEWORKS
            },
        },
        'required': ['name', 'framework', 'file_path', 'target']
    })
    def post(self, request):
        image_dir = settings.CONTAINER.AI_CONTAINER_ROOT
        image_path = local(image_dir).join(request.data['target'])

        file_path = local(request.user.workspace).join(
            request.data['file_path'])
        check_original_path(file_path)

        self._create(
            name=request.data['name'],
            image_path=str(image_path),
            framework=request.data['framework'],
            description=request.data.get('description'),
            version=request.data.get('version'),
            tags=request.data.get('tags', []),
            file_path=str(file_path)
        )
        return Response()

    def _create(self, name, image_path, framework, description, version,
                tags, file_path):
        with atomic():
            try:
                image = SingularityImage.objects.create(
                    name=name,
                    image_path=image_path,
                    framework=framework,
                    description=description,
                    version=version
                )

            except IntegrityError as e:
                logger.exception('Image has already exist')
                raise ImageAlreadyExist from e

            SingularityImageTag.objects.bulk_create([
                SingularityImageTag(image=image, index=index, name=name)
                for index, name in enumerate(tags)
            ])

        from ..tasks import copy_image
        copy_image.delay(image.id, file_path)


class AbstractImageDetailView(APIView, metaclass=ABCMeta):
    query = SingularityImage.objects

    @classmethod
    def _image_query(cls, user):
        if user.is_admin:
            # Only admin could delete or put system image
            return cls.query.filter(
                Q(username=user.username) | Q(username='')
            )
        else:
            return cls.query.filter(username=user.username)

    @classmethod
    def _query(cls, user):
        return cls.query.filter(
            Q(username=user.username) | Q(username='')
        )


class ImageDetailView(AbstractImageDetailView):

    def get(self, request, pk):
        image = self._query(request.user).get(pk=pk)
        return Response(
            image.as_dict(
                exclude=["create_time"]
            )
        )

    @json_schema_validate({
        'type': 'object',
        'properties': {
            'description': {
                'type': 'string',
                'minLength': 1,
            },
            'version': {
                'type': 'string',
                'minLength': 1,
                'maxLength': 32
            },
            'tags': {
                "type": "array",
                'items': {
                    "type": "string"
                },
            },
        }
    })
    @atomic
    def put(self, request, pk):
        image = self._image_query(request.user).\
            select_for_update().get(pk=pk)

        image.description = request.data.get('description')
        image.version = request.data.get('version')
        image.save()

        tags = request.data.get('tags', [])
        image.tags.all().delete()

        SingularityImageTag.objects.bulk_create([
            SingularityImageTag(image=image, index=index, name=name)
            for index, name in enumerate(tags)
        ])

        return Response()

    @atomic
    def delete(self, request, pk):
        image = self._image_query(request.user).get(pk=pk)
        if image.status not in [
            TaskStatus.SUCCESS.value, TaskStatus.FAILURE.value
        ]:
            raise ImageNotReady

        image_path = local(image.image_path)

        if image_path.exists():
            image_path.remove()

        image.delete()

        return Response()


class ImageReupload(AbstractImageDetailView):

    @json_schema_validate({
        'type': 'object',
        'properties': {
            'file_path': {
                'type': 'string',
                'minLength': 1,
            },
        },
        'required': ['file_path']
    })
    @atomic
    def put(self, request, pk):
        from ..utils import TaskStatus
        image = self._image_query(request.user).\
            select_for_update().get(pk=pk)

        if image.status not in [
            TaskStatus.SUCCESS.value, TaskStatus.FAILURE.value
        ]:
            raise ImageNotReady

        file_path = local(request.user.workspace).\
            join(request.data['file_path'])
        check_original_path(file_path)

        from ..tasks import copy_image
        copy_image.delay(pk, str(file_path))
        return Response()


class ImageDownload(AbstractImageDetailView):

    @json_schema_validate({
        'type': 'object',
        'properties': {
            'name': {
                'type': 'string',
                'minLength': 1
            },
            'target': {
                'type': 'string',
                'minLength': 1
            },
        },
        'required': ['name', 'target']
    })
    def post(self, request, pk):
        origin_image = self._query(request.user).get(pk=pk)

        check_original_path(local(origin_image.image_path))

        target_directory = local(request.user.workspace).join(
            request.data['target']).ensure(dir=True)

        target_path = target_directory.join(request.data['name'])

        if target_path.exists():
            raise TargetFileAlreadyExist

        from ..tasks import download_image
        download_image.delay(
            origin_path=origin_image.image_path,
            target_path=str(target_path),
            uid=request.user.uid,
            gid=request.user.gid,
        )
        return Response()


class AbstractImageEnsure(APIView, metaclass=ABCMeta):
    @abstractmethod
    def _targe_path(self, user, relpath):
        pass

    def get(self, request, name):
        target_path = self._targe_path(request.user, name)
        return Response(
            dict(exists=target_path.exists())
        )


class PrivateImageEnsure(AbstractImageEnsure):
    def _targe_path(self, user, name):
        return user_image_path(user.workspace).join(name)


class SystemImageEnsure(AbstractImageEnsure):
    permission_classes = (AsAdminRole,)

    def _targe_path(self, user, name):
        return local(
            settings.CONTAINER.AI_CONTAINER_ROOT).join(name)


class SearchSingularityImageList(SearchImageListView):

    def get_images(self):
        return SingularityImage.objects.filter(username='')
