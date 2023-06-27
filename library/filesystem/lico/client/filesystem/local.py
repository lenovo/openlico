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

import fcntl
import os
import shutil
import stat
from contextlib import contextmanager

from .base import FileSystemBaseBackend, FileSystemHandle


class LocalFileSystem(FileSystemBaseBackend):

    def __init__(self, *args, **kwargs):
        pass

    def settimeout(self, timeout):
        pass

    def walk(self, top, topdown=True, onerror=None, followlinks=False):
        return os.walk(
            top, topdown=topdown, onerror=onerror, followlinks=followlinks
        )

    def mkdir(self, path, mode=0o777):
        os.mkdir(path, mode)

    def makedirs(self, path, mode=0o777):
        os.makedirs(path, mode)

    def chown(self, path, uid, gid):
        os.chown(path, uid, gid)

    def chmod(self, path, mode):
        os.chmod(path, mode)

    def listdir(self, path):
        return os.listdir(path)

    def mknod(self, filename, mode=0o600, device=0):
        os.mknod(filename, mode, device)

    def remove(self, path):
        os.remove(path)

    def rename(self, old, new):
        os.rename(old, new)

    def chdir(self, path):
        os.chdir(path)

    def path_isreadable(self, path, uid, gid):
        s = os.stat(path)
        mode = s[stat.ST_MODE]

        if s[stat.ST_UID] == uid:
            return mode & stat.S_IRUSR > 0
        elif s[stat.ST_GID] == gid:
            return mode & stat.S_IRGRP > 0
        else:
            return mode & stat.S_IROTH > 0

    def lchown(self, path, uid, gid):
        os.lchown(path, uid, gid)

    def symlink(self, src, dst):
        os.symlink(src, dst)

    def path_getsize(self, filename):
        return os.path.getsize(filename)

    def path_getsize_without_check(self, filename):
        return self.path_getsize(filename)

    def path_exists(self, path):
        return os.path.exists(path)

    def path_isdir(self, path):
        return os.path.isdir(path)

    def path_isfile(self, path):
        return os.path.isfile(path)

    def path_abspath(self, path):
        return os.path.abspath(path)

    def path_getmtime(self, filename):
        return os.path.getmtime(filename)

    def rmtree(self, path):
        shutil.rmtree(path)

    def copytree(self, src, dst):
        shutil.copytree(src, dst)

    def copy(self, src, dst):
        shutil.copy(src, dst)

    def move(self, src, dst):
        shutil.move(src, dst)

    def copyfile(self, src, dst):
        shutil.copyfile(src, dst)

    def download_directory(self, src, dst):
        if not self.path_exists(src) or not self.path_isdir(src):
            return
        if not self.path_exists(dst):
            self.copytree(src, dst)
            return
        for sub in self.listdir(src):
            sub_path = os.path.join(src, sub)
            if self.path_isfile(sub_path):
                self.copy(sub_path, dst)
            else:
                target_path = os.path.join(dst, sub)
                self.download_directory(sub_path, target_path)

    def download_file(self, src, dst):
        self.copy(src, dst)

    def count_file_lines(self, filename, mode='r'):
        with open(filename, mode=mode) as f:
            return self._get_linenum(f)

    def read_content(self, filename, start=0, num=None, mode='r'):
        with open(filename, mode=mode) as f:
            return self._read_fp(f, start, num)

    def read_content_without_check(
            self, filename, start=0, num=None, mode='r'
    ):
        return self.read_content(filename, start, num, mode=mode)[0]

    def open_file(self, filename, mode='r'):
        return LocalFile(filename, mode)

    @contextmanager
    def write_with_lock_file(self, filename, mode='r'):
        with LocalFile(filename, mode) as lock_file:
            fcntl.flock(lock_file.file_handle, fcntl.LOCK_EX)
            try:
                yield lock_file
            finally:
                fcntl.flock(lock_file.file_handle, fcntl.LOCK_UN)

    def size(self, path):
        import psutil
        disk_usage = psutil.disk_usage(path)
        return dict(
            total=disk_usage.total,
            used=disk_usage.used
        )

    def make_zip_by_files(self, filename, files_dict):
        """
        :param filename: type string
          - new zip file abspath with name
        :param files_dict: type: dict
          - key, compression file abspath
          - value, path in zip file
        :return:
        """
        import zipfile
        try:
            with zipfile.ZipFile(filename, 'w') as zp:
                for key in files_dict:
                    zp.write(key, files_dict[key])
        except Exception as e:
            return dict(created=False,
                        reason=f'Write zip file error: {e}')
        return dict(created=True, reason='')

    def make_multi_symlinks(self, links_dict):
        """
        :param links_dict:
          key is the path of resource
          value is the link path
        :return: {"created": True, reason=''}
        """
        for src in links_dict:
            os.symlink(src, links_dict[src])
        return dict(created=True, reason='')


class LocalFile(FileSystemHandle):
    def __init__(self, name, mode, fs=None):
        self._fp = open(name, mode)

    def __enter__(self):
        return self

    def __exit__(self, *excinfo):
        self._fp.close()

    @property
    def file_handle(self):
        return self._fp

    def close(self):
        self._fp.close()
