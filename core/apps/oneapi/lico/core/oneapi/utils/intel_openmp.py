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

logger = logging.getLogger(__name__)


def drop_dim(arr):
    try:
        new_arr = []
        for i in arr:
            for j in i:
                new_arr.append(j)
        return new_arr, 1
    except TypeError:
        return arr, 0


def transpose(arr):
    try:
        new_arr = []
        for i in range(len(arr[0])):
            sub = []
            for j in arr:
                sub.append(j[i])
            new_arr.append(sub)
        return new_arr, 1
    except TypeError:
        return arr, 0


def change_arr(arr_dim2):
    tid_bind = dict()
    for tid1, proc1 in enumerate(arr_dim2):
        tid_key = str(tid1)
        for tid2, proc2 in enumerate(arr_dim2):
            if proc1 == proc2:
                if tid2 > tid1:
                    tid_key = tid_key + ',' + str(tid2)
                elif tid2 == tid1:
                    continue
                else:
                    break
        else:
            tid_bind[tid_key] = ','.join([str(p) for p in proc1])
    return tid_bind


def change_format(granularity, os_proc, arr):
    tid_bind = dict()

    if granularity != "fine" and granularity != "thread":
        os_proc_dim2, _ = drop_dim(os_proc)
        logger.debug("drop_dim os_proc_dim2={}".format(os_proc_dim2))
        arr_dim2 = []
        for i in arr:
            for one_core in os_proc_dim2:
                if i in one_core:
                    arr_dim2.append(one_core)
                    continue
        tid_bind = change_arr(arr_dim2)
    else:
        for tid, proc in enumerate(arr):
            tid_bind[str(tid)] = str(proc)
    return tid_bind
