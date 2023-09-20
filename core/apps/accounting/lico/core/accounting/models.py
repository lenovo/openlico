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


from django.db.models import (
    CASCADE, PROTECT, BigIntegerField, CharField, DateField, DecimalField,
    FloatField, ForeignKey, IntegerField,
)
from django.db.models.fields import BooleanField

from lico.core.contrib.fields import DateTimeField, JSONField
from lico.core.contrib.models import Model


class StorageBillingStatement(Model):
    path = CharField(null=False, max_length=512)
    billing_date = DateTimeField(null=False)
    username = CharField(max_length=32, db_index=True)
    bill_group_id = IntegerField()
    bill_group_name = CharField(max_length=32, db_index=True)
    storage_charge_rate = FloatField(null=False, default=1,
                                     help_text='unit:ccy per GB*day')
    storage_count = FloatField(null=False, blank=True, default=0,
                               help_text='unit:GB')
    storage_capacity = FloatField(null=False, blank=True, default=0,
                                  help_text='unit:GB')
    storage_cost = FloatField(null=False, blank=True, default=0,
                              help_text='unit:ccy')
    discount = DecimalField(null=True, blank=True, default=1,
                            max_digits=3, decimal_places=2)
    billing_cost = FloatField(null=False)
    create_time = DateTimeField(db_index=True, auto_now_add=True)
    update_time = DateTimeField(auto_now=True)


class JobBillingStatement(Model):
    job_id = CharField(null=False, max_length=32, blank=True, default="")
    job_name = CharField(null=False, max_length=128, blank=True, default="")
    scheduler_id = CharField(null=False, max_length=32, blank=True,
                             default="", db_index=True)
    submitter = CharField(null=False, max_length=32, blank=True,
                          db_index=True, default="")
    bill_group_id = IntegerField()
    bill_group_name = CharField(max_length=32, db_index=True)
    billing_runtime = IntegerField(null=False, default=0)
    record_id = CharField(null=False, max_length=32, default="")
    queue = CharField(null=False, max_length=128, blank=True, default="")
    job_create_time = DateTimeField(null=True)
    job_start_time = DateTimeField(null=True)
    job_end_time = DateTimeField(null=True)
    job_runtime = IntegerField(null=False, blank=True, default=0,
                               help_text='unit: second')
    charge_rate = FloatField(null=False, default=1,
                             help_text='unit:ccy per core*hour')
    cpu_count = FloatField(null=False, blank=True, default=0)
    cpu_cost = FloatField(null=False, blank=True, default=0)
    gres_charge_rate = JSONField(null=False, default={})
    gres_count = JSONField(null=False, blank=True, default={})
    gres_cost = JSONField(null=False, blank=True, default={})
    memory_charge_rate = FloatField(null=False, default=1,
                                    help_text='unit:ccy per MB*hour')
    memory_count = FloatField(null=False, blank=True, default=0,
                              help_text='unit:MB')
    memory_cost = FloatField(null=False, blank=True, default=0,
                             help_text='unit:ccy')
    discount = DecimalField(null=True, blank=True, default=1,
                            max_digits=3, decimal_places=2)
    total_cost = FloatField(null=False)
    billing_cost = FloatField(null=False)
    create_time = DateTimeField(db_index=True, auto_now_add=True)
    update_time = DateTimeField(auto_now=True)


class BillGroup(Model):
    HOUR = "hour"
    MINUTE = "minute"
    DISPLAY_TYPE_CHOICES = [
        (HOUR, "hour"),
        (MINUTE, "minute")
    ]
    name = CharField(null=False, default="default_bill_group",
                     max_length=20, unique=True)
    balance = FloatField(null=False, default=0)
    charged = FloatField(null=False, default=0)
    used_time = BigIntegerField(null=False, default=0)
    used_credits = FloatField(null=False, default=0)
    description = CharField(null=False, default="", blank=True, max_length=200)
    charge_rate = FloatField(null=False, default=1,
                             help_text='unit:ccy per core*hour')
    cr_minute = FloatField(null=True, blank=True,
                           help_text='unit:ccy per core*minute')
    cr_display_type = CharField(max_length=32, choices=DISPLAY_TYPE_CHOICES,
                                default=DISPLAY_TYPE_CHOICES[0][0])
    last_operation_time = DateTimeField(auto_now=True)
    gres_charge_rate = JSONField(null=False, default={})
    gcr_minute = JSONField(null=True, blank=True, default={})
    gcr_display_type = JSONField(null=False, default={})
    memory_charge_rate = FloatField(null=False, default=1,
                                    help_text='unit:ccy per MB*hour')
    mcr_minute = FloatField(null=True, blank=True,
                            help_text='unit:ccy per MB*minute')
    mcr_display_type = CharField(max_length=32, choices=DISPLAY_TYPE_CHOICES,
                                 default=DISPLAY_TYPE_CHOICES[0][0])
    storage_charge_rate = FloatField(null=False, default=1,
                                     help_text='unit:ccy per GB*day')


class BillGroupQueuePolicy(Model):
    HOUR = "hour"
    MINUTE = "minute"
    DISPLAY_TYPE_CHOICES = (
        (HOUR, "hour"),
        (MINUTE, "minute")
    )
    bill_group = ForeignKey(BillGroup, null=True, on_delete=CASCADE)
    charge_rate = FloatField(null=False, default=1,
                             help_text='unit:ccy per core*hour')
    cr_minute = FloatField(null=True, blank=True,
                           help_text='unit:ccy per core*minute')
    cr_display_type = CharField(max_length=32, choices=DISPLAY_TYPE_CHOICES,
                                default=DISPLAY_TYPE_CHOICES[0][0])
    gres_charge_rate = JSONField(null=False, default={})
    gcr_minute = JSONField(null=True, blank=True, default={})
    gcr_display_type = JSONField(null=False, default={})
    memory_charge_rate = FloatField(null=False, default=1,
                                    help_text='unit:ccy per MB*hour')
    mcr_minute = FloatField(null=True, blank=True,
                            help_text='unit:ccy per MB*minute')
    mcr_display_type = CharField(max_length=32, choices=DISPLAY_TYPE_CHOICES,
                                 default=DISPLAY_TYPE_CHOICES[0][0])
    queue_list = JSONField(null=False, default=[])
    create_time = DateTimeField(auto_now_add=True)
    last_operation_time = DateTimeField(auto_now=True)


class BillGroupStoragePolicy(Model):
    bill_group = ForeignKey(BillGroup, null=True, on_delete=CASCADE)
    storage_charge_rate = FloatField(null=False, default=1,
                                     help_text='unit:ccy per GB*day')
    path_list = JSONField(null=False, default=[])
    create_time = DateTimeField(auto_now_add=True)
    last_operation_time = DateTimeField(auto_now=True)


class Discount(Model):
    USER = "user"
    USERGROUP = "usergroup"
    TYPE_CHOICES = [
        (USER, "user"),
        (USERGROUP, "usergroup")
    ]
    type = CharField(max_length=32, null=False, choices=TYPE_CHOICES)
    name = CharField(max_length=32, null=False)
    discount = DecimalField(default=1, max_digits=3, decimal_places=2)
    create_time = DateTimeField(db_index=True, auto_now_add=True)
    update_time = DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("type", "name")


class Deposit(Model):
    BILLING_TYPE_CHOICES = [
        ('', ''),
        ('job', 'job'),
        ('storage', 'storage')
    ]

    user = CharField(null=True, max_length=32)
    # XXX delete when bill_group delete
    bill_group = ForeignKey('BillGroup', null=True, on_delete=CASCADE,
                            db_column='bill_group')
    credits = FloatField(default=0)
    apply_time = DateTimeField(null=True)
    approved_time = DateTimeField(null=True)
    billing_type = CharField(null=True, blank=True, max_length=16,
                             choices=BILLING_TYPE_CHOICES,
                             default=BILLING_TYPE_CHOICES[0][0])
    billing_id = IntegerField(null=True)
    balance = FloatField(null=False)


class Gresource(Model):
    code = CharField(max_length=30, unique=True, blank=False)
    display_name = CharField(max_length=126)
    unit = CharField(max_length=126)
    billing = BooleanField(default=True)
    create_time = DateTimeField(auto_now_add=True)
    update_time = DateTimeField(auto_now=True)


class UserBillGroupMapping(Model):
    username = CharField(max_length=32, unique=True)
    bill_group = ForeignKey(
        'BillGroup', related_name='mapping', on_delete=PROTECT
    )
    create_time = DateTimeField(auto_now_add=True)
    update_time = DateTimeField(auto_now=True)


class StorageBillingRecord(Model):
    username = CharField(max_length=32)
    billing_date = DateTimeField()
    create_time = DateTimeField(auto_now_add=True)
    update_time = DateTimeField(auto_now=True)


class BillingFile(Model):
    USER = 'user'
    CLUSTER = 'cluster'
    BILLING_TYPE_CHOICES = (
        (USER, 'user'),
        (CLUSTER, 'cluster')
    )
    DAILY = 'daily'
    MONTHLY = 'monthly'
    PERIOD_CHOICES = (
        (DAILY, 'daily'),
        (MONTHLY, 'monthly')
    )

    filename = CharField(null=False, max_length=128, default="")
    billing_type = CharField(null=False,
                             max_length=16,
                             choices=BILLING_TYPE_CHOICES)
    period = CharField(null=False, max_length=16, choices=PERIOD_CHOICES)
    username = CharField(max_length=32, db_index=True)
    billing_date = DateField(null=False)
    create_time = DateTimeField(db_index=True, auto_now_add=True)
    update_time = DateTimeField(auto_now=True)
