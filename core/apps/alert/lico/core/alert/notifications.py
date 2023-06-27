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

from itertools import chain

from django.template.loader import render_to_string
from django.utils.translation import ugettext as _


def get_alarm_info(alert):
    return {
        'name': alert.policy.name,
        'node': alert.node,
        'level': _(alert.policy.get_level_display()),
        'create_time': alert.create_time.strftime('%Y-%m-%d %H:%M'),
    }


def handle_email(alert):
    from .tasks.agent_tasks import email

    target = list(set(
        chain(
            *(
                t.email
                for t in alert.policy.targets.all()
                if t.email
            )
        )
    ))

    if target:
        email.delay(
            target=target,
            title=render_to_string('alert/mail/title.html', {
                'create_time':
                    alert.create_time.strftime('%Y-%m-%d %H:%M')
            }),
            msg=render_to_string(
                'alert/mail/message.html',
                get_alarm_info(alert)
            ),
        )


def handle_script(alert):
    from .tasks.agent_tasks import script
    target = alert.policy.script
    if target is not None:
        script.delay(
            name=alert.policy.name,
            node=alert.node,
            level=alert.policy.get_level_display(),
            target=target
        )
