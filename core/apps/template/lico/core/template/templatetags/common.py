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

register = template.Library()


@register.simple_tag
def settings():
    from django.conf import settings
    return settings


@register.simple_tag
def get_now():
    import time
    current_timestamp = int(round(time.time() * 1000))
    return current_timestamp


@register.filter
def multi(x, y):
    if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
        return None
    return x * y


@register.filter
def minus(x, y):
    if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
        return None
    return x - y


@register.filter
def devide(x, y):
    if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
        return None
    return x // y


@register.filter
def convert_myfolder(origin_path, user):
    from ..helpers.fs_operator_helper import get_fs_operator
    from ..utils.common import convert_myfolder as func
    return func(get_fs_operator(user), user, origin_path)


@register.filter
def get_item(obj, key):
    return obj.get(key)


@register.filter
def shlex_split(value):
    from shlex import split
    return split(value)


@register.simple_tag
def bind_user_share_folder():
    from django.conf import settings
    return ' '.join([
        '-B {0}'.format(folder)
        for folder in settings.LICO.USER_SHARE_DIR
    ])


@register.simple_tag
def sum_items(item1, item2):
    return item1 + item2


@register.simple_tag
def command_prog(prog):
    if str(prog).endswith('.py') or str(prog).endswith('.pyc'):
        return f'python {prog}'
    else:
        return f'{prog}'


@register.simple_tag
def generate_job_password(password_length=11):
    import random
    import string

    characters = \
        string.digits + string.ascii_letters \
        + r"""!#$%&*+,-.:;<=>?@[]^_{|}~"""
    while len(characters) < password_length:
        characters += characters

    characters = list(characters)
    random.shuffle(characters)
    return "".join(characters)[:password_length]
