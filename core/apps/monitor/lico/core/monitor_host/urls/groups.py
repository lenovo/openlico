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

from django.urls import re_path

from ..views.tendency import (
    cpu, disk, energy, job, load, memory, network, temperature,
)

category = r'(?P<category>hour|day|week|month)'
groupname = r'(?P<groupname>.+)'

urlpatterns = [
    re_path(r'^{0}/tendency/{1}/energy/$'.format(groupname, category),
            energy.GroupTendencyEnergyView.as_view()),

    re_path(r'^{0}/tendency/{1}/load/$'.format(groupname, category),
            load.GroupTendencyLoadView.as_view()),

    re_path(r'^{0}/tendency/{1}/cpu/$'.format(groupname, category),
            cpu.GroupTendencyCpuView.as_view()),

    re_path(r'^{0}/tendency/{1}/temperature/$'.format(groupname, category),
            temperature.GroupTendencyTemperatureView.as_view()),

    re_path(r'^{0}/tendency/{1}/memory/$'.format(groupname, category),
            memory.GroupTendencyMemoryView.as_view()),

    re_path(r'^{0}/tendency/{1}/disk/$'.format(groupname, category),
            disk.GroupTendencyDiskView.as_view()),

    re_path(r'^{0}/tendency/{1}/network/$'.format(groupname, category),
            network.GroupTendencyNetworkView.as_view()),

    re_path(r'^{0}/tendency/{1}/ib/$'.format(groupname, category),
            network.GroupTendencyIbView.as_view()),

    re_path(r'^{0}/tendency/{1}/job/$'.format(groupname, category),
            job.GroupTendencyJob.as_view()),

    re_path(r'^{0}/heat/latest/energy/$'.format(groupname),
            energy.GroupHeatEnergyView.as_view()),

    re_path(r'^{0}/heat/latest/load/$'.format(groupname),
            load.GroupHeatLoadView.as_view()),

    re_path(r'^{0}/heat/latest/cpu/$'.format(groupname),
            cpu.GroupHeatCpuView.as_view()),

    re_path(r'^{0}/heat/latest/temperature/$'.format(groupname),
            temperature.GroupHeatTemperatureView.as_view()),

    re_path(r'^{0}/heat/latest/memory/$'.format(groupname),
            memory.GroupHeatMemoryView.as_view()),

    re_path(r'^{0}/heat/latest/disk/$'.format(groupname),
            disk.GroupHeatDiskView.as_view()),

    re_path(r'^{0}/heat/latest/network/$'.format(groupname),
            network.GroupHeatNetworkView.as_view()),

    re_path(r'^{0}/heat/latest/job/$'.format(groupname),
            job.GroupHeatJob.as_view()),
]
