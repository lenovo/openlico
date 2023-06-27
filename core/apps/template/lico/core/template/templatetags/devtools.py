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

from django import template

from lico.core.contrib.client import Client

from ..exceptions import JupyterImageNotExist, RstudioImageNotExist

register = template.Library()


def get_jupyter_image(lang, arch):
    try:
        tags = [lang, arch] if lang else [arch]
        return Client().container_client(
        ).search_jupyter_image(tags)
    except Exception as e:
        raise JupyterImageNotExist from e


@register.simple_tag
def rstudio_image():
    try:
        return Client().container_client(
        )._search_one_image(framework='rstudio')
    except Exception as e:
        raise RstudioImageNotExist from e
