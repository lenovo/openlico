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

from django.conf import settings
from django.db import models

from lico.core.contrib.fields import DateTimeField, JSONCharField, JSONField
from lico.core.contrib.models import Model


class NotifyTarget(Model):
    name = models.CharField(max_length=255, unique=True)
    phone = JSONField()
    email = JSONField()


class Policy(Model):
    NOTSET = logging.NOTSET
    INFO = logging.INFO
    WARN = logging.WARN
    ERROR = logging.ERROR
    FATAL = logging.FATAL

    LEVEL_CHOICES = (
        (str(NOTSET), 'not set'),
        (str(INFO), 'info'),
        (str(WARN), 'warn'),
        (str(ERROR), 'error'),
        (str(FATAL), 'fatal')
    )

    ON = 'ON'
    OFF = 'OFF'

    STATUS_CHOICES = (
        (ON, 'on'),
        (OFF, 'off'),
    )

    CPUSAGE = 'CPUSAGE'
    MEMORY_UTIL = 'MEMORY_UTIL'
    TEMP = 'TEMP'
    NETWORK = 'NETWORK'
    DISK = 'DISK'
    ELECTRIC = 'ELECTRIC'
    NODE_ACTIVE = 'NODE_ACTIVE'
    HARDWARE = 'HARDWARE'
    GPU_UTIL = 'GPU_UTIL'   # gpu utilization rate
    GPU_TEMP = 'GPU_TEMP'   # gpu temperature
    GPU_MEM = 'GPU_MEM'     # gpu memory
    HARDWARE_DISCOVERY = 'HARDWARE_DISCOVERY'     # hardware changes

    METRIC_POLICY_CHOICES = (
        (CPUSAGE, 'cpusage'),
        (MEMORY_UTIL, 'memory_util'),
        (TEMP, 'tempature'),
        (NETWORK, 'network'),
        (DISK, 'disk'),
        (ELECTRIC, 'electric'),
        (NODE_ACTIVE, 'node_active'),
        (HARDWARE, 'hardware'),
        (GPU_UTIL, 'gpu_util'),
        (GPU_TEMP, 'gpu_temp'),
        (GPU_MEM, 'gpu_mem'),
        (HARDWARE_DISCOVERY, 'hardware_discovery'),
    )

    LANGUAGE_CHOICES = settings.LANGUAGES

    name = models.CharField(max_length=50, unique=True)
    metric_policy = models.CharField(
        max_length=20, choices=METRIC_POLICY_CHOICES, null=True)
    portal = JSONCharField(max_length=100)
    duration = models.DurationField()
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default=OFF)
    level = models.CharField(
        choices=LEVEL_CHOICES, max_length=2, default=NOTSET
    )
    nodes = models.TextField(default='all')
    creator = models.CharField(max_length=20)
    create_time = DateTimeField(auto_now_add=True)
    modify_time = DateTimeField(auto_now=True)
    comments = JSONField(default=[])
    targets = models.ManyToManyField(
        NotifyTarget, blank=True, symmetrical=False
    )
    language = models.CharField(max_length=10, choices=LANGUAGE_CHOICES,
                                default=settings.LANGUAGE_CODE)
    script = models.TextField(null=True)

    @classmethod
    def level_value(cls, level):
        for (n, level_value) in cls.LEVEL_CHOICES:
            if n == level:
                return level_value
        else:
            return "unknown"


class Alert(Model):
    PRESENT = 'present'
    CONFIRMED = 'confirmed'
    RESOLVED = 'resolved'
    STATUS_CHOICES = (
        (PRESENT, 'present'),
        (CONFIRMED, 'confirmed'),
        (RESOLVED, 'resolved')
    )
    policy = models.ForeignKey(Policy, on_delete=models.CASCADE)
    node = models.CharField(max_length=255)
    index = models.IntegerField(null=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=PRESENT)
    create_time = DateTimeField(auto_now_add=True, db_index=True)
    comment = models.TextField()
