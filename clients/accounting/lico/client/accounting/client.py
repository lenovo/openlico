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
from typing import List

from lico.client.contrib.client import BaseClient

from .dataclass import (
    BillGroupList, BillGroupUserList, GreSource, UserBillGroupMapping,
)

logger = logging.getLogger(__name__)


class Client(BaseClient):
    app = 'accounting'

    def notify_job_charge(self, job_info):
        response = self.put(
            self.get_url('charge/job/'),
            json=job_info
        )
        return response

    def get_user_bill_group_mapping(self, names=None):
        """
        Get the mapping relationship between user
        and billing group according to user name

        :param names: User name list .
        example:["<username1>", "<username2>", ...]
        """
        params = {} if not names else {'name': names}
        response = self.post(
            url=self.get_url("internal/user_billgroup/"),
            json=params)
        return [
            UserBillGroupMapping(
                username=username,
                bill_group_id=bill_group.get('id', ''),
                bill_group_name=bill_group.get('name', '')
            )
            for username, bill_group in response.items()
        ]

    def create_user_bill_group_mapping(self, user_billgroup_pairs: dict):
        """
        Create or update a user and billing group mapping
        relationship based on the requested data

        :param user_billgroup_pairs:Dictionary of mapping relationship
        between user name and billing group.
        example:{"<username>": <bill_group_id>}
        """
        response = self.put(
            url=self.get_url("internal/user_billgroup/"),
            json={"user_billgroup_pairs": user_billgroup_pairs}
        )

        return response

    def get_username_list(self, bill_group_list: List[int]):
        """
          Get all users of the billing group

          :param bill_group_list: billing group list
           example: [<bill_group_id>,<bill_group_id>,...]
          """
        response = self.post(
            url=self.get_url("internal/billgroup/user_list/"),
            json={"bill_group_list": bill_group_list}
        )
        return [
            BillGroupUserList(
                bill_group_id=int(bill_group),
                username_list=username_list
            )
            for bill_group, username_list in response.items()
        ]

    def get_bill_group_list(self):
        """
          Get all billing group name
          """
        response = self.get(url=self.get_url("internal/billgroup/"))
        return [
            BillGroupList(
                id=bill_group["id"],
                name=bill_group["name"]
            )
            for bill_group in response
        ]

    def get_gresource_codes(self):
        """
          Get billing gresource codes
          """
        response = self.get(url=self.get_url("internal/gresource/"))
        return [GreSource(code=code) for code in response]
