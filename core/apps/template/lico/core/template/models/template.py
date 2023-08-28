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
from os import path

from django.db.models import BooleanField, CharField, IntegerField, TextField

from lico.core.contrib.models import Model


class Template(Model):
    index = IntegerField(null=False, default=99999)
    code = CharField(null=False, unique=True, max_length=128)
    name = CharField(null=False, max_length=128)
    category = CharField(null=False, max_length=128)
    feature_code = CharField(null=False, max_length=128)
    type = CharField(null=False, max_length=128)
    description = TextField(null=True)
    enable = BooleanField(default=True)
    backend = CharField(
        default='common', null=False, max_length=128
    )  # unused
    entrance = CharField(null=False, default='false', max_length=16)
    display = BooleanField(default=True)
    subtemplate = TextField(null=True)
    location = TextField(null=False)
    params = TextField(null=True)

    @property
    def logo(self):
        return path.join(self.location, 'template.jpg')

    @property
    def help_file_en(self):
        return path.join(self.location, 'help_en.html')

    @property
    def help_file_zh(self):
        return path.join(self.location, 'help_zh.html')

    @property
    def detail(self):
        return path.join(self.location, 'template.json')

    @property
    def example(self):
        return path.join(self.location, 'example.zip')

    @property
    def schema(self):
        schema_path = path.join(self.location, 'schema.json')
        if not path.exists(schema_path):
            return {"type": "object"}
        with open(schema_path) as f:
            return json.load(f)

    @property
    def template(self):
        from django.template import Template
        with open(path.join(self.location, 'template.txt')) as f:
            return Template(f.read())

    @property
    def template_file(self):
        with open(path.join(self.location, 'template.txt')) as f:
            return f.read()

    def get_param_ids(self, data_type=None):
        with open(self.detail) as f:
            param_json = json.load(f)

        if data_type is None:
            return [
                param['id'] for param in param_json.get('params', [])
            ]
        else:
            return [
                param['id'] for param in param_json.get('params', [])
                if param['dataType'] in data_type
            ]

    def save(self, *args, **kwargs):
        with open(self.detail) as f:
            content = json.load(f)
        self.code = content["code"]
        self.name = content["name"]
        self.category = content["category"]
        self.feature_code = content["featureCode"]
        self.type = content["type"]
        self.description = content["description"]
        self.enable = content.get("enable", True)
        self.entrance = content.get("entrance", "false")
        self.display = content["display"]
        if 'backend' in content:
            self.backend = content["backend"]
        if 'subTemplates' in content:
            self.subtemplate = json.dumps(content["subTemplates"])
        if 'params' in content:
            self.params = json.dumps(content['params'])
        if 'index' in content:
            self.index = content['index']
        return super(Template, self).save(*args, **kwargs)
