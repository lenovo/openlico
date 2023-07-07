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

from django.db import models


class OperationLog(models.Model):
    USER = 'user'
    JOB = 'job'
    NODE = 'node'
    ALARM = 'alert'
    POLICY = 'policy'
    BILLGROUP = 'billgroup'
    DEPOSIT = 'deposit'
    OSGROUP = 'osgroup'
    CREATE = 'create'
    UPDATE = 'update'
    DELETE = 'delete'
    RECHARGE = 'recharge'
    CHARGEBACK = 'chargeback'
    CONFIRM = 'confirm'
    SOLVE = 'solve'
    TURN_ON = 'turn_on'
    TURN_OFF = 'turn_off'
    CANCEL = 'cancel'
    RERUN = 'rerun'
    COMMENT = 'comment'
    PRIORITY = 'priority'

    MODULE_TYPE_CHOIXES = (
        (USER, 'user'),
        (JOB, 'job'),
        (NODE, 'node'),
        (ALARM, 'alert'),
        (POLICY, 'policy'),
        (BILLGROUP, 'billgroup'),
        (DEPOSIT, 'deposit'),
        (OSGROUP, 'osgroup'),
    )

    OPERATION_TYPE_CHOICES = (
        (CREATE, 'create'),
        (UPDATE, 'update'),
        (DELETE, 'delete'),
        (RECHARGE, 'recharge'),
        (CHARGEBACK, 'chargeback'),
        (SOLVE, 'solve'),
        (CONFIRM, 'confirm'),
        (TURN_ON, 'turn_on'),
        (TURN_OFF, 'turn_off'),
        (CANCEL, 'cancel'),
        (RERUN, 'rerun'),
        (COMMENT, 'comment'),
        (PRIORITY, 'priority')
    )

    module = models.CharField(
        choices=MODULE_TYPE_CHOIXES, max_length=128, null=False, blank=False)
    operate_time = models.DateTimeField(auto_now_add=True)
    operation = models.CharField(
        choices=OPERATION_TYPE_CHOICES,
        max_length=128, null=False, blank=False)
    operator = models.CharField(max_length=256, null=False, blank=False)


class LogDetail(models.Model):
    object_id = models.IntegerField()
    name = models.CharField(
        max_length=256, null=False, blank=False
    )
    optlog = models.ForeignKey(
        'OperationLog', related_name='target', on_delete=models.PROTECT
    )


class SecretKey(models.Model):
    key = models.BinaryField(max_length=128)
    create_time = models.DateTimeField(auto_now_add=True)
    update_time = models.DateTimeField(auto_now=True)
