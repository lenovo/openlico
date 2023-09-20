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

from ..models import JobComp

JSON_SCHEMA_HOOKS = {
    "type": "array",
    "items": {
        "oneOf": [
            {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": [
                            JobComp.STARTED,
                            JobComp.COMPLETED
                        ]
                    },
                    "url": {
                        "type": "string",
                        "minLength": 1
                    },
                    "method": {
                        "type": "string",
                        "enum": ["POST", "GET", "PUT"]
                    },
                    "notice": {
                        "type": "string",
                        "enum": ["rest", "lico_restapi"]
                    },
                },
                "required": ["type", "url"]
            },
            {
                "type": "object",
                "properties": {
                    "notice": {
                        "const": "email"
                    },
                },
                "required": ["notice"]
            }
        ]
    }
}


def save_notice_job(hooks, job_id):
    for hook in hooks:
        notice_type = hook.get('notice', JobComp.REST)
        if notice_type == JobComp.EMAIL:
            kwargs = dict(
                job=job_id,
                url='',
                type=JobComp.COMPLETED,
                notice_type=notice_type
            )
        else:
            kwargs = dict(
                job=job_id,
                url=hook['url'],
                type=hook['type'],
                method=hook.get("method", "POST"),
                notice_type=notice_type
            )
        JobComp.objects.create(**kwargs)
