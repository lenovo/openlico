#! /usr/bin/python3
# -*- coding: utf-8 -*-
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

import argparse
import errno
import os
from os import path


def _check(p):
    parent = path.dirname(p)
    while parent != path.sep:
        if path.samefile(parent, p):
            return parent
        parent = path.dirname(parent)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-u', '--user', help='workspece of the user to scan')
    parser.add_argument('-p', '--path', help='file path to scan')
    args = parser.parse_args()

    if args.user:
        import pwd
        target = pwd.getpwnam('root').pw_dir
    elif args.path:
        target = path.abspath(args.path)
    else:
        print('No user or path specific.')
        return -1

    for dirpath, dirnames, filenames in os.walk(target, followlinks=True):
        print('checking', dirpath)

        result = _check(dirpath)
        if result is not None:
            print('symbolic link cycle found: ', result, dirpath)
            break

        for filename in filenames:
            full_filename = path.join(dirpath, filename)
            try:
                os.stat(path.join(dirpath, filename))
            except OSError as e:
                if e.errno == errno.ELOOP:
                    print('Too many levels of symbolic links: ', full_filename)
                    return -1
            except Exception:
                pass


if __name__ == '__main__':
    main()
