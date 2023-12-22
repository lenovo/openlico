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

import os
import sys

from django.core.management import (
    ManagementUtility, color_style, defaultdict, get_commands,
)


class LicoManagementUtility(ManagementUtility):
    def main_help_text(self, commands_only=False):
        """Return the script's main help text, as a string."""
        if commands_only:
            usage = sorted(get_commands())
        else:
            usage = [
                "",
                "Type '%s help <subcommand>' for help "
                "on a specific subcommand." % self.prog_name,
                "",
                "Available subcommands:",
            ]
            from .subapp import iter_sub_apps
            commands_dict = defaultdict(lambda: [])
            app_dict = {'lico.core.' + app_obj.name: app_obj
                        for app_obj in iter_sub_apps(active=True)}
            for command, app in get_commands().items():
                if app.startswith('lico.core.'):
                    if app in app_dict and \
                            not app_dict[app].on_load_command(command):
                        continue
                    commands_dict[app].append(command)
            style = color_style()
            for app in sorted(commands_dict):
                usage.append("")
                usage.append(style.NOTICE("[%s]" % app))
                for name in sorted(commands_dict[app]):
                    usage.append("    %s" % name)
            # Output an extra note if settings are not properly configured
            if self.settings_exception is not None:
                usage.append(style.NOTICE(
                    "Note that only Django core commands are listed "
                    "as settings are not properly configured (error: %s)."
                    % self.settings_exception))

        return '\n'.join(usage)


def set_env():
    if 'VIRTUAL_ENV' in os.environ:
        os.environ.setdefault(
            'LICO_CONFIG_FOLDER',
            os.path.join(sys.prefix, 'etc', 'lico')
        )
        os.environ.setdefault(
            'LICO_LOG_FOLDER',
            os.path.join(sys.prefix, 'log', 'lico')
        )
        os.environ.setdefault(
            'LICO_STATE_FOLDER',
            os.path.join(sys.prefix, 'state', 'lico', 'core')
        )
        os.environ.setdefault(
            'LICO_RUN_FOLDER',
            os.path.join(sys.prefix, 'run')
        )
    else:
        os.environ.setdefault('LICO_CONFIG_FOLDER', '/etc/lico')
        os.environ.setdefault('LICO_LOG_FOLDER', '/var/log/lico')
        os.environ.setdefault('LICO_STATE_FOLDER', '/var/lib/lico/core/')
        os.environ.setdefault('LICO_RUN_FOLDER', '/var/run/')

    from datetime import datetime

    from dateutil.tz import tzlocal
    if 'LICO_LOCAL_TIMEZONE_OFFSET' not in os.environ:
        os.environ['LICO_LOCAL_TIMEZONE_OFFSET'] = '{0}'.format(
            tzlocal().utcoffset(
                datetime.fromtimestamp(0)
            ).total_seconds() // 60
        )

    os.environ.setdefault('PYTHON_PREFIX', sys.prefix)
    os.environ.setdefault(
        'PYTHON_VERSION', '{0.major}.{0.minor}'.format(sys.version_info)
    )
    os.environ['DJANGO_SETTINGS_MODULE'] = 'lico.core.base.settings'

    os.environ['LICO_LOG_FOLDER'] = os.path.abspath(
        os.environ['LICO_LOG_FOLDER']
    )
    os.environ['LICO_CONFIG_FOLDER'] = os.path.abspath(
        os.environ['LICO_CONFIG_FOLDER']
    )
    os.environ['LICO_STATE_FOLDER'] = os.path.abspath(
        os.environ['LICO_STATE_FOLDER']
    )


def main():
    set_env()
    try:
        subcommand = sys.argv[1]
    except IndexError:
        subcommand = 'help'

    # show release version
    if subcommand == 'version' or sys.argv[1:] == ['--version']:
        from pkg_resources import get_distribution
        print(get_distribution('lico-core-base'))

        from .subapp import iter_sub_apps
        for app in iter_sub_apps(active=None):
            if app.active:
                print(
                    app.dist,
                    '(\033[32mactive\033[0m)'
                )
            else:
                print(
                    app.dist,
                    '(\033[31minactive\033[0m)'
                )
                for index, reason in enumerate(app.inactive_reasons, 1):
                    print(f'{index}. {reason}')

        exit()

    LicoManagementUtility(sys.argv).execute()
