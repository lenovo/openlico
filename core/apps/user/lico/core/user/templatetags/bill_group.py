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

from django import template

register = template.Library()


@register.filter
def user_bill_group_name(users_bill_group, username):
    bill_group_name = ''
    for user_bill_group in users_bill_group:
        if user_bill_group.username and user_bill_group.username == username:
            bill_group_name = user_bill_group.bill_group_name
            break

    return bill_group_name
