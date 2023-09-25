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
from typing import Callable, List

from py.path import local

logger = logging.getLogger(__name__)


class ConfigDict(dict):  # pragma: no cover
    def __getattr__(self, item):
        return self.__getitem__(item)

    def __setattr__(self, key, value):
        return self.__setitem__(key, value)


def _substitute(value, extra_settings):
    from string import Template

    if isinstance(value, str):
        return Template(value).safe_substitute(**extra_settings)
    if isinstance(value, dict):
        for k, v in value.items():
            value[k] = _substitute(v, extra_settings)
        return value
    if isinstance(value, list):
        return [_substitute(each, extra_settings) for each in value]
    return value


def update_settings(module_name, extra_settings):
    import sys
    try:
        module = sys.modules[module_name]
    except KeyError:
        __import__(module_name)
        module = sys.modules[module_name]

    for member, value in extra_settings.items():
        if member.isupper() and not member.startswith('_'):
            value = _substitute(value, extra_settings)
            setattr(module, member, value)


def load_settings(
    module_name: str,
    settings_paths: List[local],
    prefix: str = None,
    on_toml_loaded: [Callable[[ConfigDict], ConfigDict], None] = None,
    on_toml_unloaded: [Callable[[List[local]], None], None] = None
):
    import toml

    for path in settings_paths:
        if path.exists():
            settings_path = path
            break
    else:
        print(
            'Error: None of the config files exist: '
            '\033[33m{0}\033[0m'.format([
                str(settings_path)
                for settings_path in settings_paths
            ]))
        if on_toml_unloaded is not None:
            on_toml_unloaded(settings_paths)
        return

    logger.info('Load config file: %s', settings_path)
    with settings_path.open() as fd:
        try:
            config = toml.load(fd, _dict=ConfigDict)
            if on_toml_loaded is not None:
                config = on_toml_loaded(config)

        except toml.decoder.TomlDecodeError:  # pragma: no cover
            print(f'Invalid TOML configuration file: {settings_path}')
            raise

        if prefix is not None:
            update_settings(
                module_name, ConfigDict({
                    prefix: config.get(prefix, ConfigDict())
                })
            )
        else:
            update_settings(module_name, config)

