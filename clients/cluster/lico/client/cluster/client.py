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

from lico.client.contrib.client import BaseClient

from .dataclass import Group, Node, Rack, Row

logger = logging.getLogger(__name__)


class Client(BaseClient):
    app = 'cluster'

    def get_rack_nodelist(self, racks=None):
        response = self.post(
            url=self.get_url('rack/host/list/'),
            json={'racks': racks if racks is not None else []}
        )
        return [
            Rack(
                name=rack_dict['name'],
                nodes=[
                    Node(**node_dict)
                    for node_dict in rack_dict['nodes']
                ]
            )
            for rack_dict in response['racks']
        ]

    def get_group_nodelist(self):
        response = self.get(
            url=self.get_url('nodegroup/host/list/')
        )
        return [
            Group(
                name=group_dict['name'],
                nodes=[
                    Node(**node_dict)
                    for node_dict in group_dict['nodes']
                ]
            )
            for group_dict in response['groups']
        ]

    def get_nodelist(self):
        response = self.get(
            url=self.get_url('node/host/list/')
        )
        return [
            Node(**node_dict)
            for node_dict in response['nodes']
        ]

    def get_hostlist(self):
        response = self.get(
            url=self.get_url('node/host/list/')
        )
        return [
            node_dict['hostname']
            for node_dict in response['nodes']
        ]

    def get_row_racklist(self):
        response = self.get(
            url=self.get_url('row/rack/list/')
        )
        return [
            Row(
                name=row_dict['name'],
                racks=[
                    rack['name'] for rack in row_dict['racks']
                ]
            )
            for row_dict in response['rows']
        ]

    def add_room(self, name, location, on_cloud=True):
        response = self.post(
            url=self.get_url('room/internal/add/'),
            json={
                "name": name,
                "location": location,
                "on_cloud": on_cloud
            }
        )
        return response

    def delete_room(self, name):
        response = self.delete(
            url=self.get_url(f'room/internal/{name}/detail/')
        )
        return response

    def get_room(self, name):
        response = self.get(
            url=self.get_url(f'room/internal/{name}/detail/')
        )
        return response

    def add_row(self, name, index, room=None, on_cloud=True):
        data = {
            "name": name,
            "index": index,
            "on_cloud": on_cloud
        }
        if room:
            data.update(room=room)
        response = self.post(
            url=self.get_url('row/internal/add/'),
            json=data
        )
        return response

    def delete_row(self, name):
        response = self.delete(
            url=self.get_url(f'row/internal/{name}/detail/')
        )
        return response

    def get_row(self, name):
        response = self.get(
            url=self.get_url(f'row/internal/{name}/detail/')
        )
        return response

    def add_rack(self, name, col, row=None, on_cloud=True):
        data = {
            "name": name,
            "col": col,
            "on_cloud": on_cloud
        }
        if row:
            data.update(row=row)
        response = self.post(
            url=self.get_url('rack/internal/add/'),
            json=data
        )
        return response

    def delete_rack(self, name):
        response = self.delete(
            url=self.get_url(f'rack/internal/{name}/detail/')
        )
        return response

    def get_rack(self, name):
        response = self.get(
            url=self.get_url(f'rack/internal/{name}/detail/')
        )
        return response

    def add_node(
            self, hostname, type, machinetype, mgt_address, rack,
            bmc_address=None, location_u=1, chassis=None, on_cloud=True
    ):
        data = {
            "hostname": hostname,
            "type": type,
            "machinetype": machinetype,
            "mgt_address": mgt_address,
            "rack": rack,
            "location_u": location_u,
            "on_cloud": on_cloud
        }
        if bmc_address:
            data.update(bmc_address=bmc_address)
        if chassis:
            data.update(chassis=chassis)
        response = self.post(
            url=self.get_url('node/internal/add/'),
            json=data
        )
        return response

    def delete_node(self, hostname):
        response = self.delete(
            url=self.get_url(f'node/internal/{hostname}/detail/')
        )
        return response

    def get_node(self, hostname):
        response = self.get(
            url=self.get_url(f'node/internal/{hostname}/detail/')
        )
        return response

    def add_nodegroup(
            self, name, nodes=[], on_cloud=True
    ):
        data = {
            "name": name,
            "nodes": nodes,
            "on_cloud": on_cloud
        }
        response = self.post(
            url=self.get_url('nodegroup/internal/add/'),
            json=data
        )
        return response

    def delete_nodegroup(self, name):
        response = self.delete(
            url=self.get_url(f'nodegroup/internal/{name}/detail/')
        )
        return response

    def get_nodegroup(self, name):
        response = self.get(
            url=self.get_url(f'nodegroup/internal/{name}/detail/')
        )
        return response
