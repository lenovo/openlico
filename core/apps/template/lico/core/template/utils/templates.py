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

import os

from ..models import Template


def get_sub_path(template_path):
    list_catalog = os.listdir(template_path)
    for catalog in list_catalog:
        catalog_path = os.path.join(template_path, catalog)
        if os.path.isdir(catalog_path):
            yield catalog_path


def _clear_template():
    Template.objects.all().delete()


def sync(template_path_list):
    _clear_template()
    for template_path in template_path_list:
        for sub_path in get_sub_path(template_path):
            Template.objects.create(
                location=sub_path
            )


def convert_myfolder(fopr, user, origin_path):
    if not origin_path.startswith('MyFolder'):
        return origin_path
    return fopr.path_abspath(
        fopr.path_join(
            user.workspace,
            fopr.path_relpath(
                origin_path,
                start='MyFolder'
            )
        )
    )
