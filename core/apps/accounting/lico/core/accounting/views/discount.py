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

from django.db import transaction
from django.db.utils import IntegrityError
from rest_framework.response import Response

from lico.core.contrib.schema import json_schema_validate
from lico.core.contrib.views import APIView

from ..exceptions import (
    UserDiscountCreateOrUpdateException, UserDiscountNotExistException,
    UsergroupDiscountCreateOrUpdateException,
    UsergroupDiscountNotExistException,
)
from ..models import Discount

logger = logging.getLogger(__name__)


class DiscountView(APIView):
    @json_schema_validate({
        "type": "object",
        "properties": {
            'type': {
                "type": "string",
                "enum": [Discount.USER, Discount.USERGROUP]
            },
            "name": {
                "type": "string",
                "minLength": 1,
                "maxLength": 32
            },
            "discount": {
                "type": "number",
                "minimum": 0,
                "maximum": 1
            }
        },
        "required": ["type", "name", "discount"]
    })
    def post(self, request):
        type = request.data["type"]
        name = request.data["name"]
        discount = request.data["discount"]
        try:
            Discount.objects.update_or_create(
                type=type,
                name=name,
                defaults={'discount': discount}
            )
            logger.info(
                f"Successfully created or updated Discount. "
                f"The discount is type-name: {type}-{name}."
            )
            return Response()
        except IntegrityError as e:
            logger.exception(
                f"Failed to create or update Discount. "
                f"The discount is type-name: {type}-{name}."
            )
            if type == Discount.USER:
                raise UserDiscountCreateOrUpdateException from e
            else:
                raise UsergroupDiscountCreateOrUpdateException from e

    def get(self, request):
        data = [
            discount.as_dict(
                exclude=['create_time', 'update_time']
            ) for discount in Discount.objects.iterator()
        ]
        return Response({"data": data})


class DiscountDetailView(APIView):
    @json_schema_validate({
        "type": "object",
        "properties": {
            'type': {
                "type": "string",
                "enum": [Discount.USER, Discount.USERGROUP]
            },
            "name": {
                "type": "string",
                "minLength": 1,
                "maxLength": 32
            },
            "discount": {
                "type": "number",
                "minimum": 0,
                "maximum": 1
            }
        }
    })
    def put(self, request, pk):
        data = request.data
        try:
            with transaction.atomic():
                discount = Discount.objects.get(id=pk)
                discount.type = data['type']
                discount.name = data['name']
                discount.discount = data['discount']
                discount.save()
            return Response()
        except Discount.DoesNotExist as e:
            logger.exception("This discount id:%s does not exist.", pk)
            if data['type'] == Discount.USER:
                raise UserDiscountNotExistException from e
            else:
                raise UsergroupDiscountNotExistException from e

    def delete(self, request, pk):
        try:
            Discount.objects.get(id=pk).delete()
            return Response()
        except Discount.DoesNotExist:
            logger.exception("This discount id:%s does not exist.", pk)
            raise
