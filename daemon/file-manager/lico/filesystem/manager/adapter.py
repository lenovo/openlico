# -*- coding: utf-8 -*-
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
import os.path
import pwd
import stat
from abc import ABCMeta, abstractmethod

import attr
import falcon


@attr.s
class HostUser:
    username = attr.ib()
    uid = attr.ib()
    gid = attr.ib()
    workspace = attr.ib()


class BaseAdapter(metaclass=ABCMeta):
    @staticmethod
    def get_file_stat(path, followlinks=True):
        if followlinks:
            return os.stat(path)
        else:
            return os.lstat(path)

    @staticmethod
    def file_exists(path, followlinks=True):
        if followlinks:
            return os.path.exists(path)
        else:
            return os.path.lexists(path)

    @abstractmethod
    def is_readable(self, path, user, followlinks=True):
        pass

    @abstractmethod
    def is_writable(self, path, user, followlinks=True):
        pass

    @abstractmethod
    def change_owner(self, path, user, followlinks=False):
        pass

    @property
    @abstractmethod
    def key(self):
        pass

    @abstractmethod
    def get_user_info(self, username):
        pass


class HostAdapter(BaseAdapter):
    def is_readable(self, path, user, followlinks=True):
        if not self.file_exists(path, followlinks=followlinks):
            return False

        uid = user.uid
        gid = user.gid
        s = self.get_file_stat(path, followlinks=followlinks)
        mode = s[stat.ST_MODE]

        if stat.S_ISDIR(mode):
            if s[stat.ST_UID] == uid:
                return (mode & stat.S_IXUSR > 0) and (mode & stat.S_IRUSR > 0)
            elif s[stat.ST_GID] == gid:
                return (mode & stat.S_IXGRP > 0) and (mode & stat.S_IRGRP > 0)
            else:
                return (mode & stat.S_IXOTH > 0) and (mode & stat.S_IROTH > 0)
        else:
            if s[stat.ST_UID] == uid:
                return mode & stat.S_IRUSR > 0
            elif s[stat.ST_GID] == gid:
                return mode & stat.S_IRGRP > 0
            else:
                return mode & stat.S_IROTH > 0

    def is_writable(self, path, user, followlinks=True):
        if not self.file_exists(path, followlinks=followlinks):
            return False

        uid = user.uid
        gid = user.gid
        s = self.get_file_stat(path, followlinks=followlinks)
        mode = s[stat.ST_MODE]

        if stat.S_ISDIR(mode):
            if s[stat.ST_UID] == uid:
                return (mode & stat.S_IXUSR > 0) and (mode & stat.S_IWUSR > 0)
            elif s[stat.ST_GID] == gid:
                return (mode & stat.S_IXGRP > 0) and (mode & stat.S_IWGRP > 0)
            else:
                return (mode & stat.S_IXOTH > 0) and (mode & stat.S_IWOTH > 0)
        else:
            if s[stat.ST_UID] == uid:
                return mode & stat.S_IWUSR > 0
            elif s[stat.ST_GID] == gid:
                return mode & stat.S_IWGRP > 0
            else:
                return mode & stat.S_IWOTH > 0

    def change_owner(self, path, user, followlinks=False):
        if followlinks:
            os.chown(path, user.uid, user.gid)
        else:
            os.lchown(path, user.uid, user.gid)

    @property
    def key(self):
        return ''

    def get_user_info(self, username):
        try:
            _passwd = pwd.getpwnam(username)
        except KeyError as e:
            raise falcon.HTTPUnauthorized(
                description='User does not exists.'
            ) from e

        return HostUser(
            username=username,
            uid=_passwd.pw_uid,
            gid=_passwd.pw_gid,
            workspace=_passwd.pw_dir
        )
