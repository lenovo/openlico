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

from lico.core.contrib.exceptions import LicoError


class AccountingException(LicoError):
    message = 'Accounting operation error.'
    errid = 14000


class UserDiscountNotExistException(AccountingException):
    message = "This discount of this user does not exist."
    errid = 14001


class UserDiscountCreateOrUpdateException(AccountingException):
    message = "Failed to create or update the discount of this user."
    errid = 14002


class QueuePolicyAlreadySetException(AccountingException):
    message = 'The queue is already set to queue policy.'
    errid = 14003


class CreateQueuePolicyException(AccountingException):
    message = 'Failed to create bill group queue policy.'
    errid = 14004


class UsergroupDiscountNotExistException(AccountingException):
    message = "This discount of this usergroup does not exist."
    errid = 14006


class UsergroupDiscountCreateOrUpdateException(AccountingException):
    message = "Failed to create or update the discount of this usergroup."
    errid = 14007


class BillingFileNotFoundException(AccountingException):
    message = 'Billing report file not found.'
    errid = 14009


class StoragePolicyAlreadySetException(AccountingException):
    message = 'The storage is already set to storage policy.'
    errid = 14010


class CreateStoragePolicyException(AccountingException):
    message = 'Failed to create bill group storage policy.'
    errid = 14011


class CreateStorageBillingStatementException(AccountingException):
    message = 'Failed to create StorageBillingStatement.'
    errid = 14013


class CreateDepositException(AccountingException):
    message = 'Failed to create Deposit.'
    errid = 14014


class CreateStorageBillingRecordException(AccountingException):
    message = 'Failed to create CreateStorageBillingRecord.'
    errid = 14015


class JobBillingStatementDuplicatedException(AccountingException):
    message = 'The job charge Duplicated.'
    errid = 14016


class GetStorageQuotaFailedException(AccountingException):
    message = 'Failed to get storage quota.'
    errid = 14017


class QueryBillingStatementFailedException(AccountingException):
    message = 'Failed to query job and storage billing statement.'
    errid = 14018


class BillingNotGenerateException(AccountingException):
    message = 'Billing is not generated.'
    errid = 14020


class BillroupAlreadyExistsException(AccountingException):
    message = 'Bill group alreday exists.'
    errid = 14021


class InvalidMinuteChargeRateException(AccountingException):
    message = 'Invalid charge rate minute.'
    errid = 14022


class MissingMinuteChargeRateException(AccountingException):
    message = 'Failed to get charge rate minute.'
    errid = 14023


class CopyBillGroupQueuePolicyException(AccountingException):
    message = 'Copy Queue Policy failed.'
    errid = 14024


class CopyBillGroupStoragePolicyException(AccountingException):
    message = 'Copy Storage Policy failed.'
    errid = 14025


class CreateBillGroupUserRelationException(AccountingException):
    message = 'Create user and billing group relationships failed.'
    errid = 14026


class RemoveBillgroupHasMemberException(AccountingException):
    message = 'Unable to remove nonempty billing group.'
    errid = 14027


class InvalidParameterException(AccountingException):
    message = 'Accounting Invalid parameter.'
    errid = 14028


class UserBillGroupNotExistException(AccountingException):
    message = "The user has not a bill group."
    errid = 14029


class JobChargeDurationException(AccountingException):
    message = 'The job charge Duration error.'
    errid = 14030

