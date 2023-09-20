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

import sys
from typing import Iterable, List, Optional

from django.conf import LazySettings, settings
from py.path import local

from lico.core.base.subapp import AbstractApplication


class Application(AbstractApplication):
    @property
    def config_prefix(self) -> Optional[str]:
        return None

    def on_load_command(self, command):
        return settings.LICO.SCHEDULER == 'slurm' \
                or command not in ['sync_account', 'sync_account_timer']

    def on_load_settings(
            self, settings_module_name: str, arch: str
    ):
        super().on_load_settings(settings_module_name, arch)

        module = sys.modules[settings_module_name]

        from lico.auth import SharedSecret
        setattr(module, 'WEB_SECRET_KEY', SharedSecret.generate())
        web_secret_key = getattr(module, 'WEB_SECRET_KEY')

        from .synckey import SecretKeyTask
        setattr(web_secret_key, 'key_func', SecretKeyTask.get_key_from_db)

        setattr(
            module, 'AUTHENTICATION_BACKENDS',
            ('lico.core.user.pam.PamAuthBackend',)
        )

    @property
    def inactive_reasons(self) -> Iterable[str]:
        reasons = super().inactive_reasons
        if not local('/etc/pam.d/lico').exists():
            reasons.append(
                'Pam config file '
                '\033[33m/etc/pam.d/lico\033[0m '
                'not exists.',
            )
        return reasons

    def on_show_config(self, settings):
        config = super().on_show_config(settings)
        config['use_libuser'] = settings.USER.USE_LIBUSER

        return config

    def on_prepare(self, settings):
        from .models import ImportRecordTask
        ImportRecordTask.objects.update(is_running=False)

    def on_wsgi_init(self, settings: LazySettings):
        from threading import Thread

        from lico.auth.key import KeyGroup

        from .synckey import SecretKeyTask

        sync_task = SecretKeyTask()
        settings.WEB_SECRET_KEY.keys = KeyGroup(
            key_expire_day=settings.USER.KEY.EXPIRE_DAY,
            token_expire_minute=settings.USER.TOKEN.EXPIRE_MINUTES)
        sync_task.once(settings.WEB_SECRET_KEY)
        t = Thread(target=sync_task.run,
                   args=(settings.WEB_SECRET_KEY,),
                   daemon=True)
        t.start()

    def on_install_apps(
            self, install_apps: List[str], arch: str
    ):
        super().on_install_apps(install_apps, arch)

    def on_load_urls(self, urlpatterns: List, settings: LazySettings):
        super().on_load_urls(urlpatterns, settings)

    def on_init(self, settings):
        from django.core.management import call_command
        if settings.LICO.ARCH == 'host':
            call_command('share_dirs_init')
