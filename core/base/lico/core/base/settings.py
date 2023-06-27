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
import sys

from py.path import local

from .settings_toml import load_settings
from .subapp import iter_sub_apps

SECRET_KEY = '!Do not use!'

DEBUG = False

INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'rest_framework',
    'lico.core.base'
]

ALLOWED_HOSTS = []

MIDDLEWARE = []

ROOT_URLCONF = 'lico.core.base.urls'

LOGGING_CONFIG = None

builtins = []

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        "OPTIONS": {
            "debug": False,
            "string_if_invalid": "!!!ERROR!!!",
            "builtins": builtins
        }
    },
]

WSGI_APPLICATION = 'lico.wsgi.application'

LANGUAGES = (
    ('en', 'English'),
    ('sc', 'Simplified Chinese'),
)
LANGUAGE_CODE = 'en'

LOCALE_PATHS = ()

TIME_ZONE = 'UTC'

USE_I18N = True
USE_L10N = True
USE_TZ = True

REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
    ),
    'EXCEPTION_HANDLER': 'lico.core.base.plugins.exception_handler',
}


def on_toml_loaded(config):
    if 'LICO' not in config:
        print('Invalid config format.')
        exit(-1)

    # inject DATABASE into DATABASES.default
    if 'DATABASE' in config:
        if 'DATABASES' not in config:
            config.DATABASES = {}
        if config.DATABASE.ENGINE.endswith('.mysql'):
            from lico.password import fetch_pass
            db_user, db_pass = fetch_pass('mariadb')
            if db_user is not None and db_pass is not None:
                config.DATABASE.setdefault('USER', db_user)
                config.DATABASE.setdefault('PASSWORD', db_pass)
        config.DATABASES['default'] = config.DATABASE
        del config['DATABASE']

    return config


def on_toml_unloaded(settings_path):
    exit(-1)


load_settings(
    __name__, [
        local(
            os.environ['LICO_CONFIG_FOLDER']
        ).join('lico.ini')
    ],
    on_toml_loaded=on_toml_loaded,
    on_toml_unloaded=on_toml_unloaded
)

arch = sys.modules[__name__].LICO.ARCH
for app in iter_sub_apps():
    app.on_install_apps(INSTALLED_APPS, arch)
    app.on_load_settings(__name__, arch)
    app.on_load_template_builtins(builtins, arch)
