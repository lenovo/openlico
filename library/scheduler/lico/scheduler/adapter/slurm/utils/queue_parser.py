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

import re
from collections import defaultdict
from typing import List

from lico.scheduler.adapter.slurm.slurm_config import SchedulerConfig
from lico.scheduler.base.job.queue import Queue
from lico.scheduler.base.job.queue_state import QueueState
from lico.scheduler.base.tres.trackable_resource import TrackableResource
from lico.scheduler.base.tres.trackable_resource_type import (
    TrackableResourceType,
)


def get_queue_total_resource(
        queues: dict, gres_dict: dict, gres_label_info: dict,
) -> List[TrackableResource]:
    resource_list = []
    res_append = resource_list.append
    if int(queues["TOTALCPUS"]):
        res_append(TrackableResource(
            type=TrackableResourceType.CORES,
            count=int(queues["TOTALCPUS"])
        ))

    if int(queues["TOTALNODES"]):
        res_append(TrackableResource(
            type=TrackableResourceType.NODES,
            count=int(queues["TOTALNODES"])
        ))

    gres_count_dict = defaultdict(int)
    for gres, label_count in gres_label_info.items():
        if not label_count:
            continue
        for label, count in label_count.items():
            resource_list.append(TrackableResource(
                type=TrackableResourceType.GRES,
                code=gres,
                count=count,
                spec=label
            ))
            gres_count_dict[gres] += int(count)

    for gres, gres_val in gres_dict.items():
        if not gres_val[1]:
            continue
        count = int(gres_val[1]) - gres_count_dict[gres]
        if count:
            res_append(TrackableResource(
                type=TrackableResourceType.GRES,
                code=gres,
                count=count
            ))
    return resource_list


def convert_unlimit_to_negative(value):
    return -1 if value == "UNLIMITED" else float(value)


def get_queue_max_resource_per_node(
        queues: dict, gres_dict: dict, gres_per_node_max: dict,
) -> List[TrackableResource]:
    max_mem_per_node = convert_unlimit_to_negative(queues['MAXMEMPERNODE'])
    def_mem_per_node = convert_unlimit_to_negative(queues['DEFMEMPERNODE'])

    mem_per_node = [v for v in [max_mem_per_node, def_mem_per_node] if v > 0]
    mem_per_node = min(mem_per_node) if mem_per_node else "UNLIMITED"

    per_node_resource_list = []
    res_append = per_node_resource_list.append
    if queues['MAXCPUSPERNODE']:
        res_append(TrackableResource(
            type=TrackableResourceType.CORES,
            count=queues['MAXCPUSPERNODE']
        ))
    if mem_per_node:
        res_append(TrackableResource(
            type=TrackableResourceType.MEMORY,
            count=mem_per_node
        ))

    max_count_dict = defaultdict(int)
    for gres, label_count in gres_per_node_max.items():
        if not label_count:
            continue
        for label, count in label_count.items():
            res_append(TrackableResource(
                type=TrackableResourceType.GRES,
                code=gres,
                spec=label,
                count=count
            ))
            max_count_dict[gres] += int(count)

    for gres, gres_val in gres_dict.items():
        if not gres_val[0]:
            continue
        count = int(gres_val[0]) - max_count_dict[gres]
        if count:
            res_append(TrackableResource(
                type=TrackableResourceType.GRES,
                code=gres,
                count=count
            ))

    return per_node_resource_list


def get_queue_used_resource(
        alloc_cpus: int, gres_used_dict: dict,  gres_label_used_info: dict,
) -> List[TrackableResource]:
    used_resource_list = []
    used_count_dict = defaultdict(int)
    for k, v in gres_label_used_info.items():
        if not v:
            continue
        for label, count in v.items():
            used_resource_list.append(TrackableResource(
                type=TrackableResourceType.GRES,
                code=k,
                count=count,
                spec=label
            ))
            used_count_dict[k] += int(count)

    for key, value in gres_used_dict.items():
        if not value:
            continue
        count = int(value) - used_count_dict[key]
        if count:
            used_resource_list.append(TrackableResource(
                type=TrackableResourceType.GRES,
                code=key,
                count=count
            ))

    if alloc_cpus:
        used_resource_list.append(TrackableResource(
            type=TrackableResourceType.CORES,
            count=alloc_cpus
        ))
    return used_resource_list


def parse_queue_resource(
        output_data: list, output_fields: dict, config: SchedulerConfig
) -> (dict, dict, int):
    alloc_cpus = cpus = 0
    # gres_dict = {<gres_name>: (<max_count_per_node>, <total_count>)}
    gres_dict = {}
    gres_used_dict = {}
    gres_label_info = defaultdict(dict)
    gres_label_used_info = defaultdict(dict)
    gres_per_node_max = defaultdict(dict)
    for i in output_data:
        alloc_cpus += int(i.get("CPUS(A/I/O/T)").split("/")[0])
        cpus += int(i.get("CPUS(A/I/O/T)").split("/")[3])
        nodes = int(i.get("NODES"))
        for gres in config.tracking_gres_list:
            gres_data = i.get("GRES")
            gres_val = 0
            if "null" not in gres_data:
                for item in gres_data.split(","):
                    data = item.split(":")
                    if len(data) == 2 and data[0] == gres:
                        gres_val += int(data[-1])
                    elif len(data) == 3 and data[0] == gres:
                        gres_val += int(data[-1])
                        label = data[1]
                        gres_label_count = gres_label_info[gres].get(label, 0)
                        gres_label_info[gres].update({
                            label: int(data[-1]) * nodes + gres_label_count
                        })
                        gres_per_count = max(
                            int(data[-1]),
                            gres_per_node_max[gres].get(label, 0)
                        )
                        gres_per_node_max[gres].update({
                            label: gres_per_count
                        })

            if gres not in gres_dict:
                gres_dict.update(
                    {gres: (int(gres_val), int(gres_val) * nodes)}
                )
            else:
                total_gres = int(gres_val) * nodes + gres_dict[gres][1]
                if int(gres_val) > gres_dict[gres][0]:
                    gres_dict.update({gres: (int(gres_val), total_gres)})
                else:
                    gres_dict.update({gres: (gres_dict[gres][0], total_gres)})
            if "GRES_USED" in output_fields:
                gres_used = 0
                if "null" not in i.get("GRES"):
                    for item in i.get("GRES_USED", "").split(","):
                        item = re.match("([^(]*)", item).group(0) or ""
                        data = item.split(":")
                        used = int(re.match(
                            r"([\d]+)*", data[-1]).group(0) or 0)
                        if len(data) == 2:
                            gres_used += used
                        elif len(data) == 3:
                            gres_used += used
                            label = data[1]
                            gres_label_used = gres_label_used_info[gres].get(
                                label, 0)
                            gres_label_used_info[gres].update({
                                label: used * nodes + gres_label_used
                            })
                if gres not in gres_used_dict:
                    gres_used_dict.update({gres: int(gres_used) * nodes})
                else:
                    total_gres_used = int(gres_used) * nodes + \
                                      gres_used_dict[gres]
                    gres_used_dict.update({gres: total_gres_used})
    return \
        gres_dict, gres_used_dict, gres_label_info, \
        gres_label_used_info, alloc_cpus, gres_per_node_max


def parse_queue_info(sinfo_lines, partition_lines, config) -> List[Queue]:
    queues_list = []

    infos = defaultdict(list)
    output_list = [i.split() for i in sinfo_lines]
    output_fields = output_list.pop(0)[1:]

    for item in output_list:
        infos[item[0]].append(
            dict(zip(output_fields, item[1:]))
        )

    for queue_line in partition_lines:
        queue = dict(
            map(lambda x: (x.split('=')[0].upper(),
                           x.split('=')[1]), queue_line.split()))
        if queue['DEFAULT'] == 'YES':
            queue_name = queue['PARTITIONNAME'] + '*'
        else:
            queue_name = queue['PARTITIONNAME']

        if not infos.get(queue_name):
            continue

        queue_info = infos[queue_name]

        max_resource_list = [
            TrackableResource(
                type=TrackableResourceType.NODES,
                count=queue["MAXNODES"]
            )
        ]

        gres_dict, gres_used_dict, gres_label_info,\
            gres_label_used_info, alloc_cpus, gres_per_node_max = \
            parse_queue_resource(queue_info, output_fields, config)

        queues_list.append(Queue(
            name=queue['PARTITIONNAME'],
            max_time=queue['MAXTIME'],
            state=QueueState[queue['STATE']],
            resource_list=get_queue_total_resource(
                queue, gres_dict, gres_label_info),
            max_resource_list=max_resource_list,
            per_node_resource_list=get_queue_max_resource_per_node(
                queue, gres_dict, gres_per_node_max),
            used_resource_list=get_queue_used_resource(
                alloc_cpus, gres_used_dict, gres_label_used_info)
        ))
    return queues_list


def ignore_non_slurm_output(os_cmd_output, header) -> list:
    output_lines = os_cmd_output.decode().splitlines()
    while len(output_lines) > 0:
        if output_lines[0].startswith(header):
            break
        else:
            output_lines.pop(0)
    return output_lines
