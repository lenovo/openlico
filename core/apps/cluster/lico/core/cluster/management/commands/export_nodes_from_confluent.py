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
from collections import defaultdict

import pandas as pd
import requests
from django.conf import settings
from django.core.management import BaseCommand
from django.template.loader import render_to_string

__all__ = ['Command']


def print_green(string):
    print(f'\033[92m{string}\033[0m')


def print_red(string):
    print(f'\033[31m{string}\033[0m')


class Command(BaseCommand):
    help = 'Export information about nodes needed by LiCO in confluent.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--mgt_ip', default=settings.CLUSTER.CONFLUENT.HOST,
            help='Ip address of confluent management node'
        )
        parser.add_argument(
            '--mgt_port', default=settings.CLUSTER.CONFLUENT.PORT,
            help='Port of confluent management node'
        )
        parser.add_argument(
            '--user', default=settings.CLUSTER.CONFLUENT.USER,
            help='User of confluent management node'
        )
        parser.add_argument(
            '--password', default=settings.CLUSTER.CONFLUENT.PASS,
            help='Password of the specified user'
        )
        parser.add_argument(
            '--target_filename', default="export_nodes.csv",
            help='Name of the exported file'
        )
        parser.add_argument(
            '--timeout', default=600,
            help='Time to wait for data from confluent'
        )

    def handle(self, *args, **options):
        mgt_ip = options["mgt_ip"]
        mgt_port = options["mgt_port"]
        user = options["user"]
        password = options["password"]
        target_filename = options["target_filename"]
        timeout = options["timeout"]
        try:
            filename = os.path.join(
                os.getcwd(), target_filename
            )
            if os.path.exists(filename):
                msg = f"The {filename} already exists. " \
                      f"Do you want to overwrite it?\n" \
                      "Input (Y/N): "
                confirm = input(msg)
                if confirm.lower() != 'y':
                    exit(1)
            confluent_reslut = self.get_confluent_result_from_url(
                mgt_ip, mgt_port, user, password, timeout
            )
            node_info = self.get_info_from_confluent_result(
                confluent_reslut
            )
            context = self.get_context(node_info)
            node_info = render_to_string(
                "cluster/confluent_node.csv", context=context
            )
            with open(filename, "w") as f:
                f.write(node_info)
        except IOError as e:
            print_red(e)
            exit(1)
        except Exception as e:
            print_red("Unknown error: {}".format(e))
            exit(1)
        print_green(
            "The node information file exported from "
            "the confluent management node {} is {}\n"
            "It contains the following data:\n    Number "
            "of rooms: {}\n    Number of groups: {}\n    Number "
            "of rows: {}\n    Number of racks: {}\n    Number "
            "of nodes: {}\nAttention:\n    Please replace the <ipmi_user> "
            "and <ipmi_passwd> with the correct account and "
            "password.\n    Otherwise it may cause server deadlock".format(
                mgt_ip, filename, len(context["rooms"]),
                len(context["groups"]), len(context["rows"]),
                len(context["racks"]), len(context["nodes"])
            )
        )

    @staticmethod
    def get_confluent_result_from_url(
            mgt_ip, mgt_port, user, password, timeout
    ):
        try:
            url = "http://{}:{}/noderange/everything/attributes/all".format(
                mgt_ip, mgt_port
            )
            result = requests.get(
                url=url, auth=(user, password),
                headers={"Accept": "application/json"},
                timeout=timeout
            )
            confluent_reslut = result.json().get('databynode', [])
        except ValueError:
            print_red(
                "Invalid username or password."
            )
            exit(1)
        except requests.exceptions.RequestException:
            print_red(
                "The service of the specified confluent "
                "management node is incorrect"
            )
            exit(1)
        return confluent_reslut

    def get_info_from_confluent_result(self, confluent_reslut):
        node_info = defaultdict(lambda: {
            "node_name": None,
            "immip": None,
            "groups": [],
            "machine_type": None,
            "hostip": None,
            "room_name": None,
            "row_name": None,
            "rack_name": None,
            "location_u": None,
            "type": None,
            "info": None
        })
        node_data = defaultdict(lambda: {})
        for data in confluent_reslut:
            for key, value in data.items():
                node_data[key].update(value)
        for key, value in node_data.items():
            try:
                nodes_info = node_info[key]
                nodes_info["node_name"] = key
                nodes_info.update(
                    immip=value["hardwaremanagement.manager"]["value"],
                    hostip=value["net.hwaddr"]["value"],
                    groups=self.rm_everything_group(value["groups"]),
                    rack_name=value["location.rack"]["value"],
                    room_name=value["location.room"]["value"],
                    row_name=value["location.row"]["value"],
                    location_u=value["location.u"]["value"],
                    machine_type=value["id.model"]["value"],
                    type=value["type"]["value"],
                    info=value["id.serial"]["value"]
                )
            except KeyError:
                continue
        return node_info.values()

    @staticmethod
    def rm_everything_group(groups):
        return [
            group for group in groups if group != "everything"
        ]

    def get_context(self, node_info):
        """
            input --> [
                {groups:[], "node_room": " Shanghai ", ..., "info": "X"},
                ...,
                {groups:["head"], "node_room": "Shanghai", ..., "info": "X"}
            ]
            node_df -->
                        groups      node_room      ...       info
                0           []      Shanghai       ...          X
                1      [head]        Shanghai      ...          X
                .        ...              ...      ...        ...
            data -->
                        groups      node_room      ...       info
                0           []       Shanghai      ...          X
                1      [head]        Shanghai      ...          X
                .        ...              ...      ...        ...
            output -->
                dict
        """
        context = {
            "rooms": [],
            "groups": [],
            "rows": [],
            "racks": [],
            "nodes": []
        }
        if node_info:
            node_df = pd.DataFrame(node_info)
            data = self.rm_blank_space_in_node_df(node_df)
            context = {
                "rooms": self.get_room_list(data),
                "groups": self.get_group_list(data),
                "nodes": self.get_node_list(data),
                "rows": self.get_list_by_target(
                    data, "row_name", "room_name"
                ),
                "racks": self.get_list_by_target(
                    data, "rack_name", "row_name"
                ),
            }
        return context

    @staticmethod
    def rm_blank_space_in_node_df(node_df):
        column_list = node_df.columns.tolist()
        column_list.remove("groups")
        for column_name in column_list:
            node_df[column_name] = node_df[column_name].str.strip()
        return node_df

    @staticmethod
    def get_room_list(node_df):
        return node_df[[
            "room_name"
        ]].dropna().drop_duplicates().to_dict(orient="records")

    @staticmethod
    def get_group_list(node_df):
        return pd.unique(
            node_df[[
                "groups"
            ]].dropna().sum().values.tolist()[0]
        )

    @staticmethod
    def get_node_list(node_df):
        return node_df.fillna(value="").to_dict(orient="records")

    @staticmethod
    def get_list_by_target(node_df, target_name, diff_name):
        return node_df[[target_name, diff_name]].dropna(
            subset=[target_name]
        ).drop_duplicates().fillna(value="").to_dict(
            orient="records"
        )
