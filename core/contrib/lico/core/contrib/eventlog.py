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

from django.db.transaction import atomic

from lico.core.base.models import LogDetail, OperationLog

logger = logging.getLogger(__name__)


class EventLog(object):
    user = OperationLog.USER
    job = OperationLog.JOB
    node = OperationLog.NODE
    alarm = OperationLog.ALARM
    policy = OperationLog.POLICY
    billgroup = OperationLog.BILLGROUP
    deposit = OperationLog.DEPOSIT
    osgroup = OperationLog.OSGROUP
    create = OperationLog.CREATE
    update = OperationLog.UPDATE
    delete = OperationLog.DELETE
    recharge = OperationLog.RECHARGE
    chargeback = OperationLog.CHARGEBACK
    confirm = OperationLog.CONFIRM
    solve = OperationLog.SOLVE
    turn_on = OperationLog.TURN_ON
    turn_off = OperationLog.TURN_OFF
    cancel = OperationLog.CANCEL
    hold = OperationLog.HOLD
    release = OperationLog.RELEASE
    suspend = OperationLog.SUSPEND
    resume = OperationLog.RESUME
    rerun = OperationLog.RERUN
    comment = OperationLog.COMMENT
    priority = OperationLog.PRIORITY
    requeue = OperationLog.REQUEUE

    @classmethod
    def opt_create_instance(cls, targets, **kwargs):
        with atomic():
            try:
                optobj_list = []
                optobj = OperationLog.objects.create(**kwargs)
                for target in targets:
                    optobj_list.append(LogDetail(
                        object_id=target[0],
                        optlog=optobj,
                        name=target[1]
                    ))
                LogDetail.objects.bulk_create(optobj_list)
            except Exception:
                logging.exception('Fail to create opt log')

    @classmethod
    def opt_create(cls, operator, module, operation, target):
        data = {
            'operator': operator,
            'module': module,
            'operation': operation,
        }
        cls.opt_create_instance(target, **data)

    @classmethod
    def make_list(cls, id, name):
        return [(id, name)]
