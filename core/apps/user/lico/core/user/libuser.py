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
from os import path

from .exceptions import (
    InvalidGroup, InvalidOperation, InvalidUser, LibuserConfigException,
)
from .utils import require_libuser

logger = logging.getLogger(__name__)


class Libuser:

    @require_libuser
    def __init__(self):
        import libuser
        self.libuser = libuser
        try:
            self.a = self.libuser.admin(
                prompt=self.prompt_callback
            )
        except SystemError as e:
            raise LibuserConfigException from e

    @staticmethod
    def prompt_callback(prompts):  # pragma: no cover
        for p in prompts:
            if p.key == 'ldap/password':
                from lico.password import fetch_pass
                _, password = fetch_pass('ldap')
                if password is not None:
                    p.value = password
                    continue

            p.value = p.default_value

    def _make_user(self, user):
        try:
            return dict(
                name=user[self.libuser.USERNAME][0],
                uid=user[self.libuser.UIDNUMBER][0],
                gid=user[self.libuser.GIDNUMBER][0],
                shell=user[self.libuser.LOGINSHELL][0],  # nosec B604
                workspace=user[self.libuser.HOMEDIRECTORY][0]
            )
        except KeyError:
            logger.exception('Error when parse user')

    def _make_group(self, group):
        try:
            return dict(
                name=group[self.libuser.GROUPNAME][0],
                gid=group[self.libuser.GIDNUMBER][0]
            )
        except KeyError:
            logger.exception('Error when parse group')

    def add_user(self, name, password=None, group=None):
        e = self.a.initUser(name)
        group = self.a.lookupGroupByName(group)
        if group:
            e[self.libuser.GIDNUMBER] = self._make_group(group)["gid"]
        try:
            self.a.addUser(e, False, False)
        except RuntimeError:
            logger.exception('The user %s is already exist', name)
            raise
        if password:
            self.a.setpassUser(e, password, False)
        user = self._make_user(e)
        user_group = self.a.lookupGroupById(user["gid"])
        user["group"] = user_group if user_group is None \
            else self._make_group(user_group)
        return user

    def add_group(self, name):
        e = self.a.initGroup(name)
        try:
            self.a.addGroup(e)
        except RuntimeError:
            logger.exception('The group %s is already exist', name)
            raise
        return self._make_group(e)

    def get_all_groups(self):
        # return self.admin.enumerateGroups()
        # return pysss.local.group
        items = self.a.enumerateGroupsFull()
        return [
            self._make_group(item) for item in items
        ]

    def remove_user(self, name):
        e = self.a.lookupUserByName(name)
        if e is None:
            return
        try:
            remove_home = path.exists(e[self.libuser.HOMEDIRECTORY][0])
        except Exception:
            remove_home = False
        try:
            if not self.a.deleteUser(e, remove_home, True):
                logger.exception('Failed to delete user %s', name)
                raise InvalidOperation
        except RuntimeError:
            logger.warning('Failed to delete user %s', name)

    def remove_group(self, name):
        e = self.a.lookupGroupByName(name)
        if e is None:
            return
        if not self.a.deleteGroup(e):
            logger.exception(
                'Failed to delete group %s', name
            )
            raise InvalidOperation

    def modify_user_group(self, user, new_group):
        e = self.a.lookupUserByName(user)
        if e is None:
            raise InvalidUser
        uid = e[self.libuser.UIDNUMBER][0]
        old_gid = e[self.libuser.GIDNUMBER][0]
        group = self.a.lookupGroupByName(new_group)
        if group is None:
            raise InvalidGroup
        new_gid = self._make_group(
            group
        )["gid"]
        if old_gid != new_gid:
            e[self.libuser.GIDNUMBER] = new_gid
            if not self.a.modifyUser(e, False):
                logger.exception(
                    "Failed to modify user group"
                )
                raise InvalidOperation

            self.renew_user_workspace(
                old_uid=uid,
                old_gid=old_gid,
                new_uid=uid,
                new_gid=new_gid,
                workspace=e[self.libuser.HOMEDIRECTORY][0]
            )

    def renew_user_workspace(
        self, old_uid, old_gid,
        new_uid, new_gid, workspace
    ):  # pragma: no cover
        from py.path import local
        top = local(workspace)
        if top.exists():
            try:
                top.chown(new_uid, new_gid)
                for p in top.visit():
                    p_stat = p.stat()
                    if p_stat.uid == old_uid and p_stat.gid == old_gid:
                        p.chown(new_uid, new_gid)
            except Exception:
                logger.exception("Fail to renew user workspace")

    def modify_user_pass(self, user, new_pass):
        e = self.a.lookupUserByName(user)
        if e is None:
            raise InvalidUser
        if not self.a.setpassUser(e, new_pass, False):
            logger.exception(
                "Failed to modify user password"
            )
            raise InvalidOperation

    def modify_user_lock(self, username, lock):
        """Modifies the expiration date of an user account. Used to deny/allow
        SSH access of a certain user to HPC cluster

        Args:
            username (str): The name of the user account
            lock (bool): True if the user shall lose SSH access
                         False if the user shall gain SSH access
        """
        e = self.a.lookupUserByName(username)
        if e is None:
            raise InvalidUser
        # Sets the user account expiration date to 1 Jan 1970 if lock == True
        # Clears the user account expiration date if lock == False
        e[self.libuser.SHADOWEXPIRE] = 0 if lock else -1
        if not self.a.modifyUser(e, False):
            logger.exception("Failed to set user account expiration date")
            raise InvalidOperation
