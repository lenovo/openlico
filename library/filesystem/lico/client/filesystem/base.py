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

import os
from abc import ABCMeta, abstractmethod


class FileSystemBaseBackend(metaclass=ABCMeta):

    @abstractmethod
    def settimeout(self, timeout):
        pass

    @abstractmethod
    def walk(self, top, topdown=True, onerror=None, followlinks=False):
        pass

    @abstractmethod
    def mkdir(self, path, mode=0o777):
        pass

    @abstractmethod
    def makedirs(self, path, mode=0o777):
        pass

    @abstractmethod
    def chown(self, path, uid, gid):
        pass

    @abstractmethod
    def chmod(self, path, mode):
        pass

    @abstractmethod
    def listdir(self, path):
        pass

    @abstractmethod
    def mknod(self, filename, mode=0o600, device=0):
        pass

    @abstractmethod
    def remove(self, path):
        pass

    @abstractmethod
    def rename(self, old, new):
        pass

    @abstractmethod
    def chdir(self, path):
        pass

    @abstractmethod
    def path_isreadable(self, path, uid, gid):
        pass

    @abstractmethod
    def path_isexecutable(self, path, uid, gid):
        pass

    @abstractmethod
    def lchown(self, path, uid, gid):
        pass

    @abstractmethod
    def symlink(self, src, dst):
        pass

    @abstractmethod
    def path_getsize(self, filename):
        pass

    @abstractmethod
    def path_exists(self, path):
        pass

    @abstractmethod
    def path_isdir(self, path):
        pass

    @abstractmethod
    def path_isfile(self, path):
        pass

    @abstractmethod
    def path_abspath(self, path):
        pass

    @abstractmethod
    def path_getmtime(self, filename):
        pass

    def path_relpath(self, path, start=os.curdir):
        return os.path.relpath(path, start)

    def curdir(self):
        return os.curdir

    def path_join(self, a, *p):
        return os.path.join(a, *p)

    def path_splitext(self, p):
        return os.path.splitext(p)

    def path_basename(self, p):
        return os.path.basename(p)

    def path_split(self, p):
        return os.path.split(p)

    def path_dirname(self, p):
        return os.path.dirname(p)

    def _get_linenum(self, fp):
        cnt = 0
        for line in fp:
            cnt += 1
        return cnt

    def _read_fp(self, fp, start=0, num=None):
        content = b'' if 'b' in fp.mode else ''
        end_pos = start
        for idx, line in enumerate(fp):
            if num is None:
                if idx >= start:
                    content += line
            else:
                if idx < start:
                    continue
                elif idx >= start + num:
                    break
                content += line
            end_pos = idx + 1
        return content, end_pos

    @abstractmethod
    def count_file_lines(self, filename, mode='r'):
        pass

    @abstractmethod
    def read_content(self, filename, start=0, num=None, mode='r'):
        pass

    @abstractmethod
    def read_content_without_check(
            self, filename, start=0, num=None, mode='r'
    ):
        pass

    @abstractmethod
    def rmtree(self, path):
        pass

    @abstractmethod
    def copytree(self, src, dst):
        pass

    @abstractmethod
    def copy(self, src, dst):
        pass

    @abstractmethod
    def move(self, src, dst):
        pass

    @abstractmethod
    def copyfile(self, src, dst):
        pass

    @abstractmethod
    def download_directory(self, src, dst):
        pass

    @abstractmethod
    def download_file(self, src, dst):
        pass

    @abstractmethod
    def open_file(self, filename, mode):
        pass

    @abstractmethod
    def size(self, path):
        pass


class FileSystemHandle(metaclass=ABCMeta):

    @abstractmethod
    def __enter__(self):
        pass

    @abstractmethod
    def __exit__(self, *excinfo):
        pass

    @abstractmethod
    def close(self):
        pass
