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

from os import path

from setuptools import setup
from setuptools_scm import get_version
from setuptools_scm.version import guess_next_version


def lico_scheme(version):
    if not version.distance:
        return version.format_with('+openlico{tag}')

    return version.format_with(
        '+openlico{guessed}.{node}',
        guessed=version.format_next_version(guess_next_version)
    )


def static_version(version):
    with open(path.join(path.dirname(__file__), 'VERSION')) as f:
        return f.read().rstrip()


setup(
    version=get_version(
        root='../../..',
        relative_to=__file__,
        version_scheme=static_version,
        local_scheme=lico_scheme
    )
)
