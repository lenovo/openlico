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
import sys
from collections import defaultdict
from os import environ, path
from subprocess import STDOUT, CalledProcessError, check_output

from django.conf import settings
from django.core.management.base import BaseCommand

from lico.core.user.models import User
from lico.core.user.utils import users_billing_group

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'sync account information for scheduler'
    lico_bill_descr = 'lico.billing_group'

    def add_arguments(self, parser):
        parser.add_argument(
            '--log-config', action='store_true',
            help='The log config file to use.'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            default=False,
            help='Output detailed message.'
        )

    def handle(self, *args, **options):
        if options['log_config']:
            log_file_path = path.join(
                environ.get("LICO_LOG_FOLDER"), 'lico-core-beat.log'
            )
            logging.basicConfig(
                filename=log_file_path,
                level=logging.DEBUG if options['verbose'] else logging.INFO,
                format='%(asctime)s: [%(levelname)s] %(message)s'
            )
        else:
            logger.setLevel(
                logging.DEBUG if options['verbose'] else logging.INFO)
            console = logging.StreamHandler()
            console.setFormatter(logging.Formatter('%(message)s'))
            logger.addHandler(console)

        if settings.LICO.SCHEDULER != 'slurm':
            msg = 'The current scheduler is not slurm!'
            logger.warning(msg)
            sys.exit(0)

        # get all users
        user_list = User.objects.values_list('username', flat=True)

        # get the associated between users and billing for lico
        bill_user_dict = self._get_assoc_lico_user(user_list)

        # get the account for scheduler
        acc_descr_dict = self._get_acc_descr()

        # get the associated between users and accounts for scheduler
        acc_user_dict, user_acc_dict = self._get_assoc_acc_user()

        # sync account
        self._sync_account(bill_user_dict, acc_user_dict)

        # sync user
        self._sync_user(
            bill_user_dict, acc_user_dict, user_acc_dict, acc_descr_dict)

    def _get_assoc_lico_user(self, user_list):
        bill_user = set()
        bill_user_dict = defaultdict(list)
        for user_obj in users_billing_group():
            bill_user_dict[user_obj.bill_group_name].append(
                user_obj.username)
            bill_user.add(user_obj.username)
        user_without_bill = set(user_list) - bill_user
        if user_without_bill:
            bill_user_dict['root'].extend(list(user_without_bill))
        return bill_user_dict

    def _get_acc_descr(self):
        account_out = self._get_account('account,descr')
        """
        acc_descr_dict:
            {
                "root": "default root account",
                "test_bill3": 'test_bill3',
                "test_bill1": 'lico.billing_group',
                "test_bill2": 'lico.billing_group'
            }

        """
        acc_descr_dict = dict()
        if account_out:
            for account_info in account_out.split('\n'):
                account, descr = account_info.split('|')
                acc_descr_dict[account] = descr
        return acc_descr_dict

    def _get_assoc_acc_user(self):
        out = self._get_associate('account,user')
        """
            acc_user_dict:
                {
                    "test_bill_group": ['user1', 'user2'],
                    "root": ["root", 'hpcuser'],
                    "test_bill2": [""]
                    ...
                }
            user_acc_dict:
                {
                    "user1": ['test_bill1', 'test_bill2'],
                    "root": ["root"],
                    "hpcuser": ["root", "test_bill3"],
                    ...
                }

        """
        acc_user_dict = defaultdict(list)
        user_acc_dict = defaultdict(list)
        if out:
            for assoc_info in out.split('\n'):
                data = assoc_info.split('|')
                if len(data) == 2:
                    account, user = data
                    acc_user_dict[account].append(user)
                    user_acc_dict[user].append(account)
        return acc_user_dict, user_acc_dict

    def _sync_account(self, bill_user_dict, acc_user_dict):
        account_set = set(bill_user_dict.keys()) - set(acc_user_dict.keys())
        fail_account = list()
        if account_set:
            return_code, out = self._add_account(','.join(account_set))
            if return_code:
                fail_account.extend(list(account_set))
                logger.debug(out)
        if fail_account:
            """
                    acc_descr_dict:
                        {
                            "root": "default root account",
                            "test_bill3": 'test_bill3',
                            "test_bill1": 'lico.billing_group',
                            "test_bill2": 'lico.billing_group'
                        }

            """
            account_dict = self._get_acc_descr()
            fail_accounts = set(fail_account)-set(account_dict.keys())
            logger.warning(
                'Add account failed: {0}'.format(','.join(fail_accounts)))

    def _dissolve_assoc(self, add_users, user_acc, acc_descr):
        delete_users = set()
        for user in add_users:
            for old_account in user_acc.get(user, []):
                if old_account == 'root':
                    continue
                if acc_descr.get(old_account, '') == self.lico_bill_descr:
                    return_code, out = self._delete_user(user, old_account)
                    if return_code:
                        delete_users.add(user)
                        logger.debug(out)
                        continue
                    delete_msg = 'Deleted the association between ' \
                                 'the user {0} and the account ' \
                                 '{1}'.format(user, old_account)
                    logger.info(delete_msg)
        return delete_users

    def _sync_user(self, bill_user, acc_user, user_acc, acc_descr):
        fail_user = list()
        for bill, users in bill_user.items():
            add_users = set(users) - set(acc_user.get(bill, []))
            if not add_users:
                continue
            # dissolve relationship for user and account
            delete_users = self._dissolve_assoc(add_users, user_acc, acc_descr)
            add_users -= delete_users
            if not add_users:
                continue
            return_code, out = self._add_user(add_users, bill)
            if return_code:
                fail_user.extend(list(add_users))
                logger.debug(out)
                continue
            sucess_msg = 'Successfully synced: account: {0};' \
                         ' users: {1}'.format(bill, ','.join(add_users))
            logger.info(sucess_msg)
        if fail_user:
            _, user_acc_dict = self._get_assoc_acc_user()
            fail_users = set(fail_user) - set(user_acc_dict.keys())
            logger.warning(
                'Add user failed: {0}'.format(','.join(fail_users)))

    def _add_user(self, user, account):
        return_code, out = self.exec_cmd(
            ['sacctmgr', 'add', 'user', ','.join(user),
             'account={0}'.format(account), '-i'])
        return return_code, out

    def _delete_user(self, user, account):
        return_code, out = self.exec_cmd(
            ['sacctmgr', 'delete', 'user', '{0}'.format(user),
             'account={0}'.format(account), '-i'])
        return return_code, out

    def _add_account(self, account):
        return_code, out = self.exec_cmd(
            ['sacctmgr', 'add', 'account', account,
             'description={0}'.format(self.lico_bill_descr), '-i'])
        return return_code, out

    def _get_account(self, field):
        return_code, out = self.exec_cmd(
            ['sacctmgr', 'show', 'account', 'format={0}'.format(field), '-Pn'])
        if return_code:
            logger.warning(out)
            sys.exit(return_code)
        return out.strip()

    def _get_associate(self, field):
        return_code, out = self.exec_cmd(
            ['sacctmgr', 'show', 'assoc', 'format={0}'.format(field), '-Pn'])
        if return_code:
            logger.warning(out)
            sys.exit(return_code)
        return out.strip()

    def exec_cmd(self, cmd):
        return_code, output = 0, b''
        try:
            output = check_output(cmd, stderr=STDOUT)
        except FileNotFoundError as e:
            logger.warning(e)
            sys.exit(1)
        except CalledProcessError as e:
            return_code = e.returncode
            output = e.stdout
        finally:
            return return_code, output.decode()
