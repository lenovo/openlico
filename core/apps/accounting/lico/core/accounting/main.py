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

from os import path

from lico.core.base.subapp import AbstractApplication


class Application(AbstractApplication):
    def on_prepare(self, settings):
        if path.exists(settings.ACCOUNTING.GRES_FILE):
            from .utils import sync_table

            sync_table()

            if settings.LICO.SCHEDULER == 'slurm':
                from lico.scheduler.adapter.slurm.utils.manager_utils import (
                    check_gres_available,
                )

                from .utils import get_gresource_codes

                check_gres_available(get_gresource_codes(billing=False))

    def on_show_config(self, settings):
        config = super().on_show_config(settings)
        from .models import Gresource
        config['gres'] = Gresource.objects.all().as_dict()
        config['billing'] = {
            'unit': settings.ACCOUNTING.BILLING.UNIT,
        }

        return config

    def on_config_scheduler(self, scheduler, settings):
        if settings.ACCOUNTING.BILLING.get('ENABLE', True):
            # It is provisioned for testing and will be deleted later
            from dateutil import parser, tz

            from lico.core.accounting.utils import get_local_timezone

            from .tasks.balance_alert import check_balance_and_alert
            from .tasks.generate_export import charge_and_billing

            scheduler.add_executor(
                'threadpool', alias=self.name, max_workers=2
            )
            conf_time = parser.parse(settings.ACCOUNTING.BILLING.DAILY_HOUR)
            conf_time = conf_time.replace(
                tzinfo=get_local_timezone()
            ).astimezone(tz.tzutc())
            scheduler.add_job(
                func=charge_and_billing,
                trigger='cron',
                hour=int(conf_time.hour),
                minute=int(conf_time.minute),
                max_instances=1,
                executor=self.name,
            )
            scheduler.add_job(
                func=check_balance_and_alert,
                trigger="interval",
                minutes=settings.ACCOUNTING.BALANCE.ALERT_INTERVAL_MINUTES,
                executor=self.name,
                max_instances=1
            )

    def on_load_settings(self, settings_module_name, arch):
        import os
        import sys
        super().on_load_settings(settings_module_name, arch)
        module = sys.modules[settings_module_name]
        module.ACCOUNTING.BILLING.setdefault(
            'TIMEZONE_OFFSET',
            int(float(os.environ['LICO_LOCAL_TIMEZONE_OFFSET']))  # unit:minute
        )
        module.ACCOUNTING.BILLING_DIR = path.join(
            os.getenv("LICO_STATE_FOLDER"), 'billing'
        )
        module.ACCOUNTING.GRES_FILE = path.join(
            os.getenv("LICO_CONFIG_FOLDER"), 'gres.csv'
        )

    def on_init(self, settings):
        from .models import BalanceAlertSetting
        balance_setting = BalanceAlertSetting.objects.first()
        if not balance_setting:
            BalanceAlertSetting.objects.create()
