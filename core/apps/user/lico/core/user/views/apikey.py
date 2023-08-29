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

from dateutil.tz import tzutc
from rest_framework.response import Response

from lico.core.contrib.schema import json_schema_validate

from ..models import ApiKey, User
from . import APIView

logger = logging.getLogger(__name__)


class ApiKeyGenerateView(APIView):
    """
    Concrete view for generating a apikey.
    """

    def get(self, request):
        api_key = ApiKey.generate_key()
        return Response(
            dict(
                api_key=api_key
            )
        )


class ApiKeyView(APIView):
    """
     Concrete view for listing a queryset or creating a model instance or
     updating a model instance or deleting a model instance
    """

    def get(self, request):
        try:
            k = request.user.apikey
        except User.apikey.RelatedObjectDoesNotExist:
            logger.info('Could not find apikey', exc_info=True)
            return Response()
        return Response(
            k.as_dict(
                inspect_related=False,
                exclude=['create_time']
            )
        )

    @json_schema_validate({
        'type': 'object',
        'properties': {
            'expire_time': {
                'type': ['integer', 'null'],
            },
            'api_key': {
                'type': 'string',
                'minLength': 1
            }
        },
        "required": ["expire_time", "api_key"]
    })
    def post(self, request):
        import datetime
        expire_time = request.data["expire_time"]
        api_key = request.data["api_key"]
        expire_time = None \
            if expire_time is None \
            else datetime.datetime.fromtimestamp(
                expire_time / 1000, tz=tzutc())
        ApiKey.objects.update_or_create(
            user=request.user,
            defaults=dict(
                expire_time=expire_time,
                api_key=api_key,
            )
        )

        return Response()

    @json_schema_validate({
        'type': 'object',
        'properties': {
            'expire_time': {
                'type': ['integer', 'null'],
            }
        },
        "required": ["expire_time"]
    })
    def patch(self, request):
        import datetime
        expire_time = request.data["expire_time"]
        expire_time = None \
            if expire_time is None \
            else datetime.datetime.fromtimestamp(
                expire_time / 1000, tz=tzutc()
            )
        ApiKey.objects.filter(
            user=request.user
        ).update(
            expire_time=expire_time
        )
        return Response()

    def delete(self, request):
        request.user.apikey.delete()
        return Response()


class ApiKeyTestView(APIView):
    from ..authentication import ApiKeyAuthentication
    authentication_classes = (ApiKeyAuthentication,)

    def post(self, request):
        return Response()
