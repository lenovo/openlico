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

import logging
import os
import sys

import tomli
from py.path import local

from .database import Database

logger = logging.getLogger(__name__)


def _open_database(filename=None):
    if filename is None:
        if 'VIRTUAL_ENV' in os.environ:
            db_folder = local(
                sys.prefix
            ).join('etc', 'lico').ensure(dir=True)
        else:
            db_folder = local(
                '/etc/lico'
            ).ensure(dir=True)
        filename = str(db_folder.join('password-tool.ini'))
    db = open(filename, 'r')
    db = Database(db=db)
    return db


def fetch_pass(keyword: str, filename=None):
    try:
        db = _open_database(filename)
        username, password = db.get(keyword)
        return username, password
    except FileNotFoundError as e:
        logger.warning(f'Error: {e}')
        return None, None
    except tomli.TOMLDecodeError as e:
        logger.warning(f'Error: {e}')
        return None, None


def get_mariadb_account(filename):
    return fetch_pass(keyword='mariadb', filename=filename)


def get_influxdb_account(filename):
    return fetch_pass(keyword='influxdb', filename=filename)


def get_confluent_account(filename):
    return fetch_pass(keyword='confluent', filename=filename)


def get_icinga_account(filename):
    return fetch_pass(keyword='icinga', filename=filename)


def get_ldap_account(filename):
    return fetch_pass(keyword='ldap', filename=filename)


def get_datasource_account(filename):
    return fetch_pass(keyword='datasource', filename=filename)


def get_account(filename):
    return None, None
