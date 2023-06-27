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

import base64
import logging
import os

from django.conf import settings
from django.db.transaction import atomic
from django.template.loader import render_to_string
from django.utils import timezone
from py.path import local
from rest_framework.response import Response

from lico.core.contrib.schema import json_schema_validate
from lico.core.contrib.views import APIView

from ...exceptions import (
    AnotherJobRunning, BuildImageFailed, MaxJobsReached, WorkSpaceNotExists,
)
from ..models import CustomImage, CustomInfo

logger = logging.getLogger(__name__)


class BuildImageView(APIView):

    def get(self, request):
        try:
            image = CustomImage.objects.get(username=request.user.username)
        except CustomImage.DoesNotExist:
            return Response(dict())
        resp = image.as_dict(
            exclude=["id", "username", "job_id"]
        )
        for item in resp.pop('custom_info'):
            resp.update({item['key']: item['value']})
        return Response(resp)

    @json_schema_validate({
        "oneOf": [
            {
                'type': 'object',
                'properties': {
                    'name': {
                        'type': 'string',
                        'minLength': 1,
                        'maxLength': 100
                    },
                    'workspace': {
                        'type': 'string',
                        'minLength': 1,
                        'maxLength': 255
                    },
                    'source': {
                        'const': 3
                    },
                    'definition_file': {
                        'type': 'string',
                        'minLength': 1,
                    },
                    'docker': {
                        'type': 'object',
                        'properties': {
                            'username': {
                                'type': 'string',
                                'minLength': 1
                            },
                            'password': {
                                'type': 'string',
                                'minLength': 1
                            }
                        },
                        'required': ['username', 'password']
                    },
                    'use_https': {
                        'type': 'boolean'
                    }
                },
                'required': ['name', 'workspace', 'source', 'definition_file']
            },
            {
                'type': 'object',
                'properties': {
                    'name': {
                        'type': 'string',
                        'minLength': 1,
                        'maxLength': 100
                    },
                    'workspace': {
                        'type': 'string',
                        'minLength': 1,
                        'maxLength': 255
                    },
                    'source': {
                        'type': 'integer',
                        'enum': [1, 2, 4, 5]
                    },
                    'image_path': {
                        "type": "string",
                        'minLength': 1,

                    },
                    'docker': {
                        'type': 'object',
                        'properties': {
                            'username': {
                                'type': 'string',
                                'minLength': 1
                            },
                            'password': {
                                'type': 'string',
                                'minLength': 1
                            }
                        },
                        'required': ['username', 'password']
                    },
                    'use_https': {
                        'type': 'boolean'
                    },
                    'packages': {
                        'type': 'object',
                        'properties': {
                            'libraries': {
                                'type': 'string',
                                'minLength': 1
                            },
                            'command': {
                                'type': 'string',
                                'minLength': 1
                            }
                        },
                        'required': ['libraries', 'command']
                    },
                },
                'required': ['name', 'workspace', 'source', 'image_path']
            }
        ]
    })
    @atomic
    def post(self, request):
        # check image state
        user = request.user
        from lico.core.contrib.client import Client
        client = Client().task_client()
        image = self._check_image_state(user.username, client)  # keep lock

        # prepare params
        source = request.data['source']
        name = request.data['name']
        workspace = request.data['workspace']
        use_https = request.data.get('use_https', True)
        docker = request.data.get('docker', dict())

        if not local(workspace).exists():
            raise WorkSpaceNotExists

        log_file = local(workspace).join(f"{name}.log")
        target_image_path = local(workspace).join(name)
        custom_info_hooks = [
            lambda image: CustomInfo(
                image=image, key='use_https', value=use_https
            )
        ]
        if docker:
            custom_info_hooks.append(
                lambda image: CustomInfo(
                    image=image, key='docker', value=docker
                )
            )

        if source == CustomImage.DEFINITION:
            config_file = request.data['definition_file']
            self._handle_definition_source(
                request, log_file, config_file, custom_info_hooks
            )

        else:
            from os import path
            no_suffix_name = path.splitext(name)[0]
            config_file = local(workspace).join(f'{no_suffix_name}.def')
            self._handle_other_source(
                request, source, log_file, config_file, custom_info_hooks
            )

        from ..utils import get_singularity_path
        docker_name = docker.get('username', '')
        docker_pwd = base64.b64decode(docker.get('password', '')).decode()
        script = render_to_string(
            "script.sh",
            {'docker_name': docker_name,
             'docker_pwd': docker_pwd,
             'use_https': not use_https,
             'singularity': get_singularity_path(),
             'image_path': str(target_image_path),
             'config_file': str(config_file),
             'cache_dir': settings.CONTAINER.SINGULARITY_CACHEDIR,
             'tmp_dir': settings.CONTAINER.SINGULARITY_TMPDIR,
             })
        user_info = dict(username=user.username, user_workspace=user.workspace)
        workspace_relpath = os.path.relpath(
            workspace, start=user.workspace
        )
        prepare = {
            "workspace": [
                {
                    "src": workspace,
                    "dst": f"workspace/{workspace_relpath}"
                }
            ]
        }
        run = {
            "cmd": "/bin/bash", "script": script, "stdout": str(log_file)
        }
        output = [{"dst": str(target_image_path)}, {"dst": str(log_file)}]

        if target_image_path.exists():
            target_image_path.remove()
        # build image
        job_id = self._build_image(
            user_info, prepare, run, output, client
        )

        # save image
        if image is not None:
            image.custom_info.all().delete()
        new_image, _ = CustomImage.objects.update_or_create(
            username=user.username,
            defaults=dict(
                name=name,
                source=source,
                workspace=workspace,
                job_id=job_id,
                log_file=str(log_file),
                create_time=timezone.now()
            )
        )
        CustomInfo.objects.bulk_create(
            [
                hook(new_image) for hook in custom_info_hooks
            ]
        )

        return Response()

    @staticmethod
    def _handle_definition_source(
            request, log_file, config_file, custom_info_hooks
    ):
        from ..utils import check_definition_validity

        check_definition_validity(config_file, request.user.workspace)

        log_file.write(f"Base From: definition file\n"
                       f"Definition Files Path: {config_file}\n")

        custom_info_hooks.append(
            lambda image: CustomInfo(
                image=image, key='definition_file', value=config_file
            )
        )

    def _handle_other_source(
            self, request, source, log_file, config_file,
            custom_info_hooks
    ):

        image_path = request.data['image_path']
        packages = request.data.get('packages')

        self._generate_log(
            source, image_path, log_file, config_file, packages
        )

        self._handle_template(source, packages, image_path, config_file)

        if packages is not None:
            custom_info_hooks.append(
                lambda image: CustomInfo(
                    image=image, key='packages', value=packages
                )
            )
        custom_info_hooks.append(
            lambda image: CustomInfo(
                image=image, key='image_path', value=image_path
            )
        )

    @staticmethod
    def _generate_log(source, image_path, log_file, config_file, packages):

        library_dict = {
            CustomImage.DOCKER: f"docker://{image_path}",
            CustomImage.SINGULARITY: f"library://{image_path}",
        }
        base_from = library_dict.get(source, image_path)

        libraries = packages['libraries'] if packages is not None else ''

        python_libs = f'Python Libs: [{libraries}]\n' if libraries else ''

        log_file.write(f"Base From: {base_from}\n"
                       f"Definition Files Path: {str(config_file)}\n"
                       f"{python_libs}")

    @staticmethod
    def _handle_template(source, packages, image_path, config_file):

        template = {
            CustomImage.DOCKER: 'docker.def',
            CustomImage.SINGULARITY: 'singularity.def',
        }.get(source, 'local_image.def')

        if packages is not None:
            libraries = packages['libraries'].replace(',', ' ')
            cmd = packages['command'].strip()
        else:
            cmd, libraries = None, None

        config_file.write(
            render_to_string(
                template, {'image_path': image_path,
                           "cmd": cmd, "libraries": libraries}
            )
        )

    @staticmethod
    def _build_image(user, prepare, run, output, client):
        from lico.client.task.exception import MaxJobsReachedError
        try:
            res = client.build_job(
                user=user, prepare=prepare, run=run, output=output
            )
        except MaxJobsReachedError as e:
            raise MaxJobsReached from e
        except Exception as e:
            raise BuildImageFailed from e
        return res

    @staticmethod
    def _check_image_state(username, client):
        image = CustomImage.objects.select_for_update().filter(
            username=username
        ).first()
        if image is not None:
            res = client.query_job_state(job_id=image.job_id)
            if res['status'] not in ['EXECUTED', 'ERROR', None]:
                logger.warning('%s is building', image.name, exc_info=True)
                raise AnotherJobRunning
        return image

    def put(self, request):
        from lico.core.contrib.client import Client
        client = Client().task_client()
        image = CustomImage.objects.get(
            username=request.user.username
        )
        client.cancel_job(job_id=image.job_id)

        local(image.log_file).write("\nBuild Canceled.", mode='a')
        return Response()


class BuildImageDetailView(APIView):

    def get(self, request):

        STATUS_MAP = dict(
            PENDING='pending',
            SUBMITTED='running',
            EXECUTED='completed',
            ERROR='failed'
        )
        resp = dict(status='unknown', max_jobs=0, running_jobs=0)
        try:
            image = CustomImage.objects.get(username=request.user.username)
        except CustomImage.DoesNotExist:
            resp.update(status=None)
            return Response(resp)
        from lico.core.contrib.client import Client
        client = Client().task_client()
        try:
            res = client.query_state()
        except Exception:
            return Response(resp)

        if image.job_id in res['status']:
            job_state = res.pop('status')[image.job_id]
            status = STATUS_MAP[job_state]
            resp.update(status=status, **res)
        return Response(resp)


class BuildImageEnsure(APIView):
    def post(self, request):
        image_path = request.data['image_path']
        return Response(
            dict(exists=local(image_path).exists())
        )
