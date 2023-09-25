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
import logging
from abc import ABCMeta, abstractmethod

from jsonschema import ValidationError, validate
from rest_framework.response import Response
from rest_framework.views import APIView as BaseAPIView

from .authentication import (
    JWTInternalAnonymousAuthentication, RemoteJWTWebAuthentication,
)
from .exceptions import InvalidJSON
from .permissions import AsUserRole, IsAuthenticated

__all__ = ["APIView", "InternalAPIView", "DataTableView"]

logger = logging.getLogger(__name__)


class APIView(BaseAPIView, metaclass=ABCMeta):
    authentication_classes = (
        RemoteJWTWebAuthentication,
    )
    permission_classes = (AsUserRole, )
    hidden_permission_classes = ()

    def get_permissions(self):
        permission_classes = super().get_permissions()
        permission_classes.extend(
            [permission() for permission in self.hidden_permission_classes]
        )
        return permission_classes


class InternalAPIView(BaseAPIView, metaclass=ABCMeta):
    authentication_classes = (
        JWTInternalAnonymousAuthentication,
    )
    permission_classes = (IsAuthenticated, )


class BaseDataTableView(BaseAPIView, metaclass=ABCMeta):
    columns_mapping = {}
    _SCHEMA = {
        "type": "object",
        "properties": {
            'offset': {
                'type': 'number',
                'minimum': 0
            },
            'length': {
                'type': 'number',
                'minimum': 0
            },
            'sort': {
                'type': 'object',
                'properties': {
                    'prop': {
                        'type': 'string'
                    },
                    'order': {
                        'type': "string",
                        'enum': ["descend", "ascend"]
                    }
                },
                "required": ['prop', 'order']
            },
            "filters": {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        "prop": {
                            "type": "string"
                        },
                        "type": {
                            'type': "string",
                            'enum': ["in", "range", "not_in"]
                        },
                        "values": {
                            "type": "array",
                            "minItems": 0
                        }
                    },
                    "required": ["prop", "type", "values"]
                },
                'minItems': 0
            },
            "search": {
                "type": "object",
                "properties": {
                    "props": {
                        "type": "array",
                        "minItems": 1
                    },
                    "keyword": {
                        "type": "string",
                    }
                },
                "required": ["props", "keyword"]
            }
        },
        "required": ["offset", "length", "filters"]
    }

    def get(self, request, *args, **kwargs):
        param_args = json.loads(
            request.query_params["args"]
        )
        self.check_param(param_args)
        param_args = self.params(request, param_args)
        query = self.get_query(request, *args, **kwargs)
        query = self.filters(query, param_args.get('filters', []))  # filter
        query = self.global_search(query, param_args)
        query = self.global_sort(query, param_args)

        filtered_total = 0 if query is None else query.count()
        offset = param_args['offset'] \
            if param_args['offset'] < filtered_total else 0
        results = [] if query is None else \
            query[offset:offset + param_args['length']]
        offset = offset + len(results)
        return Response(
            {
                'offset': offset,
                'total': filtered_total,
                'data': [self.trans_result(result) for result in results],
            }
        )

    def params(self, request, args):
        return args

    @abstractmethod
    def trans_result(self, result):
        pass

    @abstractmethod
    def get_query(self, request, *args, **kwargs):
        pass

    def global_search(self, query, param_args):
        if 'search' not in param_args or query is None:
            return query
        else:
            search = param_args['search']
            props = search['props']
            keyword = search['keyword']

            if not keyword:
                return query

            search_dict = {}
            for field in props:
                prop = self.columns_mapping.get(field, field)
                search_dict[prop] = keyword
            return query.ci_search(**search_dict)

    def global_sort_fields(self, param_args):
        sort = param_args.get("sort")
        if sort:
            if sort['prop'] in self.columns_mapping:
                prop = self.columns_mapping[sort['prop']]
            else:
                prop = sort['prop']
            return [
                ('' if sort['order'] == 'ascend' else '-') + prop
            ]
        else:
            return ['id']

    def global_sort(self, query, param_args):
        return query if query is None else query.order_by(
            *self.global_sort_fields(param_args)
        )

    def filters(self, query, filters):
        for field in filters:
            if field['prop'] in self.columns_mapping:
                prop = self.columns_mapping[field['prop']]
            else:
                prop = field['prop']

            if field['type'] == 'not_in':
                query = query.exclude(
                    **{
                        prop + '__{}'.format(
                            "in"): field['values']
                    }
                ) if len(field['values']) > 0 and query else query
            else:
                query = query.filter(
                    **{
                        prop + '__{}'.format(
                            field['type']): field['values']
                    }
                ) if len(field['values']) > 0 and query else query
        return query

    @classmethod
    def check_param(cls, param_args):
        try:
            validate(param_args, cls._SCHEMA)
        except ValidationError as e:
            logger.exception('Invalid jsonschema')
            raise InvalidJSON(e) from e


class DataTableView(APIView, BaseDataTableView, metaclass=ABCMeta):
    pass

