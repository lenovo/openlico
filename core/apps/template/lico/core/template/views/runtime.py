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

import calendar
import json
import logging

from django.db import transaction
from django.db.models import Q
from django.db.utils import IntegrityError
from rest_framework.response import Response
from rest_framework.status import HTTP_204_NO_CONTENT

from lico.core.contrib.schema import json_schema_validate
from lico.core.contrib.views import APIView

from ..exceptions import (
    RuntimeAlreadyExist, RuntimeNotExist, ScriptFileDuplicateException,
)
from ..models import Runtime, RuntimeEnv, RuntimeModule, RuntimeScript
from ..utils.runtime import runtime_distinct, script_filter

logger = logging.getLogger(__name__)


class RuntimeListView(APIView):

    def get(self, request):
        with transaction.atomic():
            if request.query_params.get('role') == 'admin':
                return Response({
                    "data": [{
                        'pk': runtime.id,
                        'name': runtime.name,
                        'username': runtime.username,
                        "tag": runtime.tag,
                        "type": runtime.type,
                        'ctime': calendar.timegm(
                            runtime.create_time.timetuple()
                        ),
                        'modules': [
                            {
                                'module': item.module,
                                'parents': item.parents_list
                            }
                            for item in runtime.modules.order_by(
                                'index'
                            ).iterator()
                        ],
                        'envs': [
                            {
                                'name': env.name,
                                'value': env.value
                            }
                            for env in runtime.envs.order_by(
                                'index'
                            ).iterator()
                        ],
                        'scripts': [
                            script.filename
                            for script in runtime.scripts.order_by(
                                'index'
                            ).iterator()
                        ],
                    }
                        for runtime in Runtime.objects.filter(
                            username=''
                        ).iterator()
                    ]
                })
            else:
                return Response({
                    "data": [{
                        'pk': runtime.id,
                        'name': runtime.name,
                        "tag": runtime.tag,
                        "username": runtime.username,
                        "type": runtime.type,
                        'ctime': calendar.timegm(
                            runtime.create_time.timetuple()
                        ),
                        'modules': [
                            {
                                'module': item.module,
                                'parents': item.parents_list
                            }
                            for item in runtime.modules.order_by(
                                'index'
                            ).iterator()
                        ],
                        'envs': [
                            {
                                'name': env.name,
                                'value': env.value
                            }
                            for env in runtime.envs.order_by(
                                'index'
                            ).iterator()
                        ],
                        'scripts': [
                            script.filename
                            for script in runtime.scripts.order_by(
                                'index'
                            ).iterator()
                        ]
                    }
                        for runtime in Runtime.objects.filter(
                            Q(username=request.user.username) | Q(username='')
                        ).iterator()
                    ]
                })

    @json_schema_validate({
        "type": "object",
        "properties": {
            "name": {
                "type": "string"
            },
            "tag": {
                "type": "string"
            },
            "type": {
                "type": "string"
            },
            "modules": {
                "type": "array",
                'items': {
                    'type': 'object',
                    "properties": {
                        "module": {
                            "type": "string"
                        },
                        "parents": {
                            "type": "array",
                            "items": {
                                "type": "string",
                            }
                        }
                    },
                    "required": ["module", "parents"]
                },
            },
            "envs": {
                "type": "array",
                'items': {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            'minLength': 1
                        },
                        "value": {
                            "type": "string",
                        }
                    },
                    "required": ["name", "value"]
                }
            },
            "scripts": {
                "type": "array",
                'items': {
                    "type": "string"
                }
            },
        },
        "required": ["name", "modules", "envs"]
    })
    def post(self, request):
        type = request.data.get('type')
        scripts = request.data.get('scripts')
        tag = request.data.get('tag')
        runtime_type = type if type else 'Runtime'
        tag = script_filter(scripts, tag)
        pk = self._create(
            request,
            request.user,
            request.data['name'],
            tag,
            request.data['modules'],
            request.data['envs'],
            runtime_type,
            scripts
        )
        return Response({"pk": pk})

    def _create(
            self, request, user, name, tag, modules,
            envs, type, scripts):
        with transaction.atomic():
            try:
                if request.query_params.get('role') == 'admin':
                    runtime = Runtime.objects.create(
                        name=name, username="",
                        tag=tag, type=type
                    )
                else:
                    runtime = Runtime.objects.create(
                        name=name, username=user.username,
                        tag=tag, type=type
                    )
            except IntegrityError as e:
                logger.exception('Runtime has already exist')
                raise RuntimeAlreadyExist from e

            for index, item in enumerate(modules):
                parents = item['parents']
                RuntimeModule.objects.create(
                    runtime=runtime,
                    index=index,
                    module=item['module'],
                    parents=None if len(parents) == 0 else ','.join(parents)
                )

            for index, env in enumerate(envs):
                RuntimeEnv.objects.create(
                    runtime=runtime,
                    index=index,
                    name=env['name'],
                    value=env['value']
                )

            try:
                for index, script in enumerate(scripts):
                    RuntimeScript.objects.create(
                        runtime=runtime,
                        index=index,
                        filename=script
                    )
            except IntegrityError as e:
                logging.exception('Script file is not allowed to be repeated')
                raise ScriptFileDuplicateException from e
            return runtime.id


class RuntimeDetailView(APIView):

    def get(self, request, pk):
        with transaction.atomic():
            try:
                runtime = Runtime.objects.filter(
                    Q(username=request.user.username) |
                    Q(username='')
                ).get(id=pk)
            except Runtime.DoesNotExist as e:
                raise RuntimeNotExist from e

            return Response({
                'pk': runtime.id,
                'name': runtime.name,
                'username': runtime.username,
                'tag': runtime.tag,
                'type': runtime.type,
                'ctime': calendar.timegm(
                    runtime.create_time.timetuple()
                ),
                'modules': [
                    {
                        'module': item.module,
                        'parents': item.parents_list
                     }
                    for item in runtime.modules.order_by(
                        'index'
                    ).iterator()
                ],
                'envs': [
                    {
                       'name': env.name,
                       'value': env.value
                    }
                    for env in runtime.envs.order_by(
                        'index'
                    ).iterator()
                ],
                'scripts': [
                    script.filename
                    for script in runtime.scripts.order_by(
                        'index'
                    ).iterator()
                ]
            })

    def delete(self, request, pk):
        with transaction.atomic():
            try:
                if request.user.is_admin:
                    Runtime.objects.filter(
                        Q(username=request.user.username) |
                        Q(username='')
                    ).get(id=pk).delete()
                else:
                    Runtime.objects.filter(
                        username=request.user.username
                    ).get(id=pk).delete()
            except Runtime.DoesNotExist as e:
                raise RuntimeNotExist from e
            return Response(status=HTTP_204_NO_CONTENT)

    @json_schema_validate({
        "type": "object",
        "properties": {
            "name": {
                "type": "string"
            },
            "tag": {
                "type": "string"
            },
            "type": {
                "type": "string"
            },
            "modules": {
                "type": "array",
                'items': {
                    'type': 'object',
                    "properties": {
                        "module": {
                            "type": "string"
                        },
                        "parents": {
                            "type": "array",
                            "items": {
                                "type": "string",
                            }
                        }
                    },
                    "required": ["module", "parents"]
                },
            },
            "envs": {
                "type": "array",
                'items': {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            'minLength': 1
                        },
                        "value": {
                            "type": "string",
                        }
                    },
                    "required": ["name", "value"]
                }
            },
            "scripts": {
                "type": "array",
                'items': {
                    "type": "string",
                }
            },
        },

        "required": ["name", "modules", "envs"]
    })
    def put(self, request, pk):
        type = request.data.get('type')
        scripts = request.data.get('scripts')
        tag = request.data.get('tag')
        runtime_type = type if type else 'Runtime'
        tag = script_filter(scripts, tag)
        self._update(
            request,
            request.data['name'],
            tag,
            request.data['modules'],
            request.data['envs'],
            pk,
            runtime_type,
            scripts,
        )
        return Response(status=HTTP_204_NO_CONTENT)

    def _update(self, request, name, tag, modules, envs, pk, type, scripts):
        with transaction.atomic():
            try:
                if request.user.is_admin:
                    runtime = Runtime.objects.filter(
                        Q(username=request.user.username) |
                        Q(username='')
                    ).select_for_update().get(pk=pk)
                else:
                    runtime = Runtime.objects.filter(
                        username=request.user.username
                    ).select_for_update().get(pk=pk)
            except Runtime.DoesNotExist as e:
                raise RuntimeNotExist from e
            self._save(runtime, name, tag, modules, envs, type, scripts)

    def _save(self, runtime, name, tag, modules, envs, type, scripts):
        try:
            runtime.name = name
            runtime.tag = tag
            runtime.type = type
            runtime.save()
        except IntegrityError as e:
            logger.exception('Runtime has already exist')
            raise RuntimeAlreadyExist from e
        runtime.modules.all().delete()
        runtime.envs.all().delete()
        runtime.scripts.all().delete()
        for index, item in enumerate(modules):
            parents = item['parents']
            RuntimeModule.objects.create(
                runtime=runtime,
                index=index,
                module=item['module'],
                parents=None if len(parents) == 0 else ','.join(parents)
            )

        for index, env in enumerate(envs):
            RuntimeEnv.objects.create(
                runtime=runtime,
                index=index,
                name=env['name'],
                value=env['value']
            )

        try:
            for index, script in enumerate(scripts):
                RuntimeScript.objects.create(
                    runtime=runtime,
                    index=index,
                    filename=script
                )
        except IntegrityError as e:
            logging.exception("Script file is not allowed to be repeated")
            raise ScriptFileDuplicateException from e


class RuntimeVerifyView(APIView):
    def post(self, request, pk):
        from lico.core.template.utils.lmod import verify_modules
        modules = (
            module.module
            for module in
            RuntimeModule.objects.filter(
                runtime__username=request.user.username
            ).filter(
                runtime__id=pk
            ).order_by('index')
        )
        verify_modules(request.user, modules)

        return Response()


class RuntimeDistinctDetailListView(APIView):

    def get(self, request):
        runtime_ids = request.query_params.get('runtime_ids')
        runtime_list = json.loads(runtime_ids)

        runtime_queryset = Runtime.objects.filter(
            Q(username=request.user.username) |
            Q(username='')
        ).filter(id__in=runtime_list)

        if len(runtime_list) == len(runtime_queryset):
            module_list, env_list, script_list = runtime_distinct(runtime_list)

            return Response({
                "modules": module_list,
                "envs": env_list,
                "scripts": script_list,
            })
        raise RuntimeNotExist
