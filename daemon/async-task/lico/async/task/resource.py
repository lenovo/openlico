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
import pwd
import uuid

from falcon.media.validators import jsonschema
from py.path import local

from .exception import MaxJobsReached
from .manager import BuildJobManager
from .utils import get_fs_operator

logger = logging.getLogger(__name__)


class FakeBuildJobDetail:
    def on_get(self, req, resp, *args, **kwargs):
        resp.media = {
            'status': None
        }

    def on_delete(self, req, resp, *args, **kwargs):
        resp.media = {}


class BuildJob:
    def __init__(
            self, builder: str, manager: BuildJobManager,
            namespace: str
    ):
        self.builder = builder
        self.manager = manager
        self.namespace = namespace

    def on_get(self, req, resp):
        resp.media = {
            'host': self.builder,
            'max_jobs': self.manager.max_jobs,
            'running_jobs': self.manager.running_jobs,
            'status': {
                f'{self.builder}/{job_id}': status.value
                for job_id, status in self.manager.records.items()
            },
            'infos': self.manager.infos
        }

    def handle_param(self, data, user, log_path, output):
        # handle workspace
        try:
            user_info = pwd.getpwnam(user["username"])
        except KeyError:
            logger.warning(
                f'Can not find user {user["username"]}',
                exc_info=True
            )
            raise
        namespace = self.namespace if self.namespace else user_info.pw_dir
        tmp_workspace = f"{namespace}/{uuid.uuid4()}"

        local(tmp_workspace).ensure_dir()

        res_data = []
        for item in data:
            if item['dst'].startswith("workspace/"):
                item['dst'] = item['dst'].replace(
                    'workspace', tmp_workspace, 1
                )
            if item['src'].startswith("MyFolder/"):
                item['src'] = item['src'].replace(
                    'MyFolder', user['user_workspace'], 1
                )
            res_data.append(item)

        # handle log
        if log_path.startswith("workspace/"):
            log_path = log_path.replace('workspace', tmp_workspace, 1)

        local(log_path).dirpath().ensure_dir()

        # handle output
        output_list = []
        for path in output:
            if path['dst'].startswith("MyFolder/"):
                path['dst'] = path['dst'].replace(
                    'MyFolder', user["user_workspace"], 1
                )
            if path.get('src') and path['src'].startswith('workspace/'):
                path['src'] = path['src'].replace(
                    'workspace', tmp_workspace, 1
                )
            output_list.append(path)

        return tmp_workspace, log_path, output_list, res_data, user_info

    @jsonschema.validate({
        'type': 'object',
        'properties': {
            'user': {
                'type': 'object',
                'properties': {
                    'username': {
                        'type': 'string',
                        'minLength': 1,
                    },
                    'user_workspace': {
                        'type': 'string',
                        'minLength': 1,
                    },
                    'user_context': {
                        'type': 'object',
                        'properties': {
                            'options': {
                                'type': 'object',
                                'properties': {
                                    'webdav_hostname': {
                                        'type': 'string',
                                        'minLength': 1,
                                    },
                                    'webdav_root': {
                                        'type': 'string',
                                        'minLength': 1,
                                    },
                                },
                                'required': ['webdav_hostname', 'webdav_root']
                            },
                            'target': {
                                'type': 'string',
                                'minLength': 1,
                            },
                            'namespace': {
                                'type': 'string',
                                'minLength': 1,
                            },
                            'pvc': {
                                'type': 'string',
                                'minLength': 1,
                            },
                        },
                        'required': ['options', 'target', 'namespace', 'pvc']
                    },
                },
                'required': ['username', 'user_workspace']
            },
            'prepare': {
                'type': 'object',
                'properties': {
                    'workspace': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'src': {
                                    'type': 'string',
                                    'minLength': 1,
                                },
                                'dst': {
                                    'type': 'string',
                                    'minLength': 1,
                                },
                            },
                            'required': ['src', 'dst']
                        }
                    },
                },
                'required': ['workspace']
            },
            'run': {
                'type': 'object',
                'properties': {
                    'cmd': {
                        "anyOf": [
                            {
                                "type": "string",
                                "minLength": 1
                            },
                            {
                                "type": "array",
                                "items": {
                                    "type": "string",
                                    "minLength": 1
                                }
                            }
                        ]
                    },
                    'script': {
                        'type': 'string',
                        'minLength': 1,
                    },
                    'stdout': {
                        'type': 'string',
                        'minLength': 1,
                    },
                },
                'required': [
                    'cmd', 'script', 'stdout'
                ]
            },
            'output': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'src': {
                            'type': 'string',
                            'minLength': 1,
                        },
                        'dst': {
                            'type': 'string',
                            'minLength': 1,
                        },
                        'auto-sync': {
                            'type': 'boolean',
                        },
                    },
                    'required': ['dst']
                }
            }
        },
        'required': [
            'user', 'prepare', 'run', 'output'
        ]
    })
    def on_post(self, req, resp):
        if self.manager.max_jobs > self.manager.running_jobs:
            fs = get_fs_operator()
            workspace, log_path, output, data, user = self.handle_param(
                req.media['prepare']['workspace'], req.media['user'],
                req.media['run']['stdout'], req.media['output']
            )

            job = self.manager.add_job(
                fs=fs,
                user=user,
                log_path=log_path,
                args=req.media['run']['cmd'],
                workspace=workspace,
                data=data,
                output=output,
                input=req.media['run']['script'].encode(),
            )

            resp.media = {
                'id': f'{self.builder}/{job.id}'
            }
        else:
            raise MaxJobsReached


class BuildJobDetail:

    def __init__(self, manager: BuildJobManager):
        self.manager = manager

    def on_get(self, req, resp, host, id):
        status = self.manager.records.get(id)
        resp.media = {
            'error': self.manager.errors.get(id),
            'status': status.value if status is not None else None
        }

    def on_delete(self, req, resp, host, id):
        self.manager.cancel_job(job_id=id)
        resp.media = {}
