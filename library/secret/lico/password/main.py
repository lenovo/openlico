"""
LiCO Password Tool

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

Usage:
  lico-password-tool [options]
  lico-password-tool (-h | --help)
  lico-password-tool --version

Options:
  -h --help             Show this screen.
  --version             Show version.
  --mariadb             Get mariadb account from configuration file.
  --confluent           Get confluent account from configuration file.
  --influxdb            Get influxdb account from configuration file.
  --icinga              Get icinga account from configuration file.
  --ldap                Get ldap account from configuration file.
  --datasource          Get datasource account from configuration file.
  --filename FILENAME   The configuration file path.
"""

from docopt import docopt


def main():
    arguments = docopt(__doc__, version='LiCO Password Tool 3.0.0')

    filename = arguments.get('--filename')

    if arguments['--mariadb']:
        from .passwd import get_mariadb_account as account
    elif arguments['--confluent']:
        from .passwd import get_confluent_account as account
    elif arguments['--influxdb']:
        from .passwd import get_influxdb_account as account
    elif arguments['--icinga']:
        from .passwd import get_icinga_account as account
    elif arguments['--ldap']:
        from .passwd import get_ldap_account as account
    elif arguments['--datasource']:
        from .passwd import get_datasource_account as account
    else:
        from .passwd import get_account as account

    username, password = account(filename=filename)
    print(f'({username}),({password})')
