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

from lico.client.contrib.client import BaseClient
from lico.client.contrib.exception import NotFound

from .dataclass import Image

logger = logging.getLogger(__name__)


class Client(BaseClient):
    app = 'container'

    def __init__(
        self,
        url: str = 'http://127.0.0.1:18080/api/',
        *args, **kwargs
    ):
        super().__init__(url, *args, **kwargs)

    def search_images(self, image_name=None, framework=None, tags=()):
        data = dict()
        if image_name:
            data.update(image_name=image_name)
        if framework:
            data.update(framework=framework)
        if tags:
            data.update(tags=list(set(tags)))
        reponse = self.post(
            url=self.get_url('search/'),
            json=data
        )
        return [
            Image(**image) for image in reponse["images"]
        ]

    def _search_one_image(
            self, image_name=None, framework=None, tags=()
    ):
        images = self.search_images(image_name, framework, tags)
        if images:
            return images[0].image_path
        else:
            raise NotFound

    def search_jupyter_image(self, tags):  # pragma: no cover
        return self._search_one_image(
            tags=tags, framework="jupyter"
        )

    def search_tensorflow_image(self, image_name):  # pragma: no cover
        try:
            tensorflow_image = self._search_one_image(
                image_name=image_name, framework='tensorflow'
            )
        except NotFound:
            tensorflow_image = self._search_one_image(
                image_name='tensorflow', framework='tensorflow'
            )
        return tensorflow_image

    def search_tensorflow2_image(self, image_name):  # pragma: no cover
        try:
            tensorflow2_image = self._search_one_image(
                image_name=image_name, framework='tensorflow2'
            )
        except NotFound:
            tensorflow2_image = self._search_one_image(
                image_name='tensorflow2', framework='tensorflow2'
            )
        return tensorflow2_image
