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

import copy
import logging

logger = logging.getLogger(__name__)


def Listcut(listTemp, n):
    try:
        return [listTemp[i:i+n] for i in range(0, len(listTemp), n)]
    except (Exception):
        return []


def get_numinfo_list(sockets_per_node, cores_per_socket, hyper_threading):
    phy_cpu_num_list = [i for i in range(
        sockets_per_node * cores_per_socket)]
    if hyper_threading is True:
        re_phy_cpu_num_list = phy_cpu_num_list[:]
        for index, cpu in enumerate(re_phy_cpu_num_list):
            phy_cpu_num_list.insert(
                index*2+1, cpu+sockets_per_node*cores_per_socket)
        cpu_num_list = phy_cpu_num_list
        cpu_info_list = Listcut(Listcut(cpu_num_list, 2), cores_per_socket)
    else:
        cpu_num_list = phy_cpu_num_list
        cpu_info_list = Listcut(Listcut(cpu_num_list, 1), cores_per_socket)
    return cpu_num_list, cpu_info_list


def get_mpiomp_cpu_list(sockets_per_node, cores_per_socket, hyper_threading):
    cpu_num_list, cpu_info_list = get_numinfo_list(
        sockets_per_node, cores_per_socket, hyper_threading)
    return cpu_num_list, cpu_info_list


def get_mpi_cpu_list(sockets_per_node, cores_per_socket,
                     list_procset, hyper_threading):
    phy_cpu_num_list = [i for i in range(
        sockets_per_node * cores_per_socket)]

    if list_procset == 'all':
        cpu_num_list, cpu_info_list = get_numinfo_list(
            sockets_per_node, cores_per_socket, hyper_threading)

    if list_procset == 'allcores':
        cpu_num_list = phy_cpu_num_list[:]
        cpu_info_list = Listcut(Listcut(cpu_num_list, 1), cores_per_socket)

    if list_procset == 'allsocks':
        cpu_num_list = phy_cpu_num_list[::cores_per_socket]
        cpu_info_list = Listcut(Listcut(cpu_num_list, 1), 1)

    return cpu_num_list, cpu_info_list


def scatter_threading(pid_bind_cpu_list, mpi_openmp_new_list_cores,
                      mpi_openmp_new_list_threads, cores_per_socket,
                      sockets_per_node, cpu_info_list, domain_size,
                      cpu_num_list):
    for j in range(cores_per_socket):
        for i in range(sockets_per_node):
            mpi_openmp_new_list_cores.append(cpu_info_list[i][j][0])
            mpi_openmp_new_list_threads.append(cpu_info_list[i][j][1])
    logger.debug("mpi_openmp_new_list_cores={}".format(
        mpi_openmp_new_list_cores))
    logger.debug("mpi_openmp_new_list_threads={}".format(
        mpi_openmp_new_list_threads))
    if len(mpi_openmp_new_list_cores) % domain_size != 0:
        per_num = domain_size - \
            len(mpi_openmp_new_list_cores) % domain_size
        logger.debug("per_num={}".format(per_num))
        for i in range(len(mpi_openmp_new_list_cores)//domain_size):
            pid_bind_cpu_list.append(
                mpi_openmp_new_list_cores[i*domain_size:(i+1)*domain_size])
            # try:
            pid_bind_cpu_list.append(
                mpi_openmp_new_list_threads[per_num + i*domain_size:
                                            per_num + (i+1)*domain_size])
            # except(Exception):
            #     pass

        pid_bind_cpu_list.append(mpi_openmp_new_list_cores[-(
            domain_size-per_num):]+mpi_openmp_new_list_threads[:per_num])
        if (len(mpi_openmp_new_list_threads) - per_num) >= domain_size and sum(
                [len(i) for i in pid_bind_cpu_list]) < len(cpu_num_list):
            after_num = (len(mpi_openmp_new_list_threads) -
                         per_num) % domain_size
            logger.debug("after_num={}".format(after_num))
            if after_num != 0:
                pid_bind_cpu_list.append(
                    mpi_openmp_new_list_threads[-after_num:])
    else:
        for i in range(len(mpi_openmp_new_list_cores)//domain_size):
            pid_bind_cpu_list.append(
                mpi_openmp_new_list_cores[i*domain_size:(i+1)*domain_size])
            pid_bind_cpu_list.append(
                mpi_openmp_new_list_threads[i*domain_size:(i+1)*domain_size])
    return pid_bind_cpu_list


def scatter_no_threading(
        mpi_openmp_new_list_cores, cores_per_socket, sockets_per_node,
        domain_size, cpu_info_list, pid_bind_cpu_list, cpu_num_list):
    for j in range(cores_per_socket):
        for i in range(sockets_per_node):
            mpi_openmp_new_list_cores.append(
                cpu_info_list[i][j][0])
    for i in range(len(mpi_openmp_new_list_cores) // domain_size):
        pid_bind_cpu_list.append(
            mpi_openmp_new_list_cores[i*domain_size:(i+1)*domain_size])
    if sum([len(i) for i in pid_bind_cpu_list]) < len(cpu_num_list):
        new_pid_bind = copy.deepcopy(cpu_num_list)
        for i in pid_bind_cpu_list:
            for j in i:
                new_pid_bind.remove(j)
        pid_bind_cpu_list.append(new_pid_bind)
    return pid_bind_cpu_list


def get_mpi_openmp_scatter(
        cpu_num_list, cpu_info_list, domain_size, pid_bind_cpu_list,
        sockets_per_node, cores_per_socket, hyper_threading,
        mpi_openmp_new_list_cores, mpi_openmp_new_list_threads):
    if domain_size == 1:
        pid_bind_cpu_list = [[i]for i in cpu_num_list]
    elif domain_size <= sockets_per_node*cores_per_socket:
        if hyper_threading:
            pid_bind_cpu_list = scatter_threading(
                pid_bind_cpu_list, mpi_openmp_new_list_cores,
                mpi_openmp_new_list_threads, cores_per_socket,
                sockets_per_node, cpu_info_list, domain_size,
                cpu_num_list)

        else:
            pid_bind_cpu_list = scatter_no_threading(
                mpi_openmp_new_list_cores, cores_per_socket,
                sockets_per_node, domain_size, cpu_info_list,
                pid_bind_cpu_list, cpu_num_list)

    elif domain_size < len(cpu_num_list):
        cpu_list = [i for i in range(len(cpu_num_list))]
        pid_bind_cpu_list.append(cpu_list[:domain_size])
        pid_bind_cpu_list.append(cpu_list[domain_size:])
    elif domain_size >= len(cpu_num_list):
        pid_bind_cpu_list = [[i for i in range(len(cpu_num_list))]]
    logger.debug("pid_bind_cpu_list={}".format(pid_bind_cpu_list))
    return pid_bind_cpu_list


def get_mpi_openmp_info(domain_size=4, domain_layout='platform',
                        cores_per_socket=8, hyper_threading=True,
                        sockets_per_node=2):

    affinity_env = {'OMP_NUM_THREADS': '{}'.format(
        domain_size), 'I_MPI_PIN_DOMAIN': '{}:{}'.format(
            domain_size, domain_layout)}

    cpu_num_list, cpu_info_list = get_mpiomp_cpu_list(
        sockets_per_node, cores_per_socket, hyper_threading)

    logger.debug("cpu_num_list={}".format(cpu_num_list))
    logger.debug("cpu_info_list={}".format(cpu_info_list))

    mpi_openmp_new_list_cores = []
    mpi_openmp_new_list_threads = []
    pid_bind_cpu_list = []
    pid_bind = {}

    try:
        if domain_layout == 'compact':
            if domain_size > len(cpu_num_list):
                domain_size = len(cpu_num_list)
            for pid in range(len(cpu_num_list)//domain_size):
                pid_bind[str(pid)] = str(
                    cpu_num_list[pid*domain_size:(pid+1)*domain_size])[1:-1]

            pid_bind_value_list = []
            for pid_bind_key, pid_bind_value in pid_bind.items():
                pid_bind_value_list.append(pid_bind_value)
            slurm_num = len(cpu_num_list)//len(pid_bind_value_list)
            pid_bind = {}
            for pid, slurm_pid_bind in enumerate(
                    pid_bind_value_list*slurm_num):
                pid_bind[str(pid)] = str(slurm_pid_bind)

        if domain_layout == 'scatter':
            pid_bind_cpu_list = get_mpi_openmp_scatter(
                cpu_num_list, cpu_info_list,
                domain_size, pid_bind_cpu_list,
                sockets_per_node, cores_per_socket,
                hyper_threading,
                mpi_openmp_new_list_cores,
                mpi_openmp_new_list_threads)
            slurm_num = len(cpu_num_list)//len(pid_bind_cpu_list)
            slurm_pid_bind_cpu_list = pid_bind_cpu_list*slurm_num
            for pid, slurm_pid_bind in enumerate(
                    slurm_pid_bind_cpu_list):
                pid_bind[str(pid)] = str(slurm_pid_bind)[1:-1]

            # if len(pid_bind_cpu_list) == len(cpu_num_list):
            #     for pid, slurm_pid_bind in enumerate(
            #             slurm_pid_bind_cpu_list):
            #         pid_bind[str(pid)] = str(slurm_pid_bind)
            # else:
            #     for pid, slurm_pid_bind in enumerate(
            #             slurm_pid_bind_cpu_list):
            #         pid_bind[str(pid)] = str(slurm_pid_bind)[1:-1]

    except ZeroDivisionError:
        logger.debug("WARNING: Invalid Equation ZeroDivisionError")
        pid_bind = {}

    logging.debug("pid_bind={}".format(pid_bind))
    return [affinity_env, cpu_info_list, pid_bind]


def list_preoffset_pinning_cpu(
        pinning_cpu, list_preoffset, list_shift,
        use_cpu_num_list, list_grain, cpu_num, processor_num):
    i = 0
    offset = list_preoffset*list_grain
    cpu_num_list_offset = use_cpu_num_list[offset:] + use_cpu_num_list[:offset]
    grain_shift = list_grain * list_shift
    new_pinning_cpu = []
    while True:
        try:
            for g in range(list_grain):
                pinning_cpu.append(
                    cpu_num_list_offset[i * grain_shift + g])
                new_pinning_cpu.append(
                    cpu_num_list_offset[i * grain_shift + g])
            i += 1
        except (Exception):
            cpu_num_list_offset = cpu_num_list_offset[list_grain:] + \
                cpu_num_list_offset[:list_grain]
            i = 0
        if len(pinning_cpu) >= cpu_num:
            cpu_num_list_offset = use_cpu_num_list[offset:] + \
                use_cpu_num_list[:offset]
            pinning_cpu = []
            i = 0
        if len(new_pinning_cpu) >= processor_num:
            break
    return new_pinning_cpu


def list_postoffset_pinning_cpu(
        pinning_cpu, list_postoffset, use_cpu_num_list, list_grain,
        cpu_num, list_shift, processor_num):
    i = 0
    j = 0
    use_cpu_num_list = [use_cpu_num_list[c:c+list_grain]
                        for c in range(0, len(use_cpu_num_list),
                                       list_grain)]
    new_cpu_num_list = []
    new_pinning_cpu = []
    while True:
        if len(new_cpu_num_list) >= cpu_num/list_grain:
            break
        new_cpu_num_list = new_cpu_num_list + use_cpu_num_list[i::list_shift]
        i += 1

    while True:
        if len(new_pinning_cpu) >= processor_num:
            break
        if j == 0:
            for n in new_cpu_num_list[list_postoffset:]:
                pinning_cpu = pinning_cpu + n
                new_pinning_cpu = new_pinning_cpu + n
            j += 1
        if j > 0:
            for n in new_cpu_num_list[j-1:]:
                pinning_cpu = pinning_cpu + n
                new_pinning_cpu = new_pinning_cpu + n
                print(new_pinning_cpu)

        if len(pinning_cpu) >= cpu_num:
            pinning_cpu = []
            j = 0
        j += 1
    return new_pinning_cpu


def list_nooffset_pinning_cpu(
        pinning_cpu, use_cpu_num_list, list_grain,
        cpu_num, processor_num, list_shift):
    i = 0
    use_cpu_num_list = [
        use_cpu_num_list[c:c+list_grain]
        for c in range(0, len(use_cpu_num_list), list_grain)]
    new_cpu_num_list = []
    new_pinning_cpu = []
    while True:
        new_cpu_num_list = use_cpu_num_list[i::list_shift]
        for p in new_cpu_num_list:
            pinning_cpu = pinning_cpu + p
            new_pinning_cpu = new_pinning_cpu + p
        i += 1

        if len(pinning_cpu) >= cpu_num:
            i = 0
            pinning_cpu = []
        if len(new_pinning_cpu) >= processor_num:
            break
    return new_pinning_cpu


def get_mpi_info(list_procset='all', list_grain=1, list_shift=1,
                 list_preoffset=0, list_postoffset=0, cores_per_socket=8,
                 hyper_threading=True, sockets_per_node=2):
    affinity_env = {'I_MPI_PIN_PROCESSOR_LIST':
                    '{}:grain={},shift={},preoffset={},postoffset={}'
                    .format(list_procset, list_grain, list_shift,
                            list_preoffset, list_postoffset)}
    cpu_num_list, cpu_info_list = get_numinfo_list(
        sockets_per_node, cores_per_socket, hyper_threading)
    logger.debug("cpu_num_list={}".format(cpu_num_list))
    logger.debug("cpu_info_list={}".format(cpu_info_list))

    use_cpu_num_list, use_cpu_info_list = get_mpi_cpu_list(
        sockets_per_node, cores_per_socket, list_procset, hyper_threading)
    logger.debug("use_cpu_num_list={}".format(use_cpu_num_list))
    logger.debug("use_cpu_info_list={}".format(use_cpu_info_list))

    cpu_num = processor_num = len(use_cpu_num_list)
    try:
        if list_procset == 'allsocks':
            if hyper_threading:
                processor_num = sockets_per_node * cores_per_socket * 2
            else:
                processor_num = sockets_per_node * cores_per_socket
        if processor_num % list_grain != 0 or list_grain >= processor_num:
            list_grain = 1
            logging.debug(
                "incorrect grain value, should be multiple of {}".format(
                    processor_num))

        pinning_cpu = []
        if list_preoffset != 0:
            new_pinning_cpu = list_preoffset_pinning_cpu(
                pinning_cpu, list_preoffset, list_shift,
                use_cpu_num_list, list_grain, cpu_num, processor_num)

        elif list_postoffset != 0:
            new_pinning_cpu = list_postoffset_pinning_cpu(
                pinning_cpu, list_postoffset, use_cpu_num_list, list_grain,
                cpu_num, list_shift, processor_num)

        else:
            new_pinning_cpu = list_nooffset_pinning_cpu(
                pinning_cpu, use_cpu_num_list, list_grain,
                cpu_num, processor_num, list_shift)

        pid_bind = {}
        new_pinning_cpu1 = []
        if list_procset == 'allcores' and hyper_threading is True:
            new_pinning_cpu1 = new_pinning_cpu[:processor_num] * 2
            new_pinning_cpu = new_pinning_cpu1
        for pid, cpu in enumerate(new_pinning_cpu):
            pid_bind[str(pid)] = str(cpu)
    except ZeroDivisionError:
        logger.debug("WARNING: Invalid Equation ZeroDivisionError")
        pid_bind = {}
    logging.debug("pid_bind={}".format(pid_bind))

    return [affinity_env, cpu_info_list, pid_bind]


def T_cpu_info_list(cpu_info_list):
    L = []
    for each in map(list, zip(*cpu_info_list)):
        print(each)
        L = L+each
    logger.debug("L={}".format(L))
    return L


def modify_cpu_info_list(cpu_list):
    for sub_list in cpu_list:
        for i_sub_list in sub_list:
            i_sub_list[0] = sub_list[0][0]
    cpu_list = T_cpu_info_list(cpu_list)
    cpu_list = sum(cpu_list, [])
    logger.debug("modify_cpu_list={}".format(cpu_list))
    return cpu_list


def allsocks_cpu_info_list(cpu_info_list):
    cpu_list = copy.deepcopy(cpu_info_list)
    logger.debug("cpu_list={}".format(cpu_list))
    # try:
    if len(cpu_list[0][0]) >= 2:
        for sub_list in cpu_list:
            for i_sub_list in sub_list:
                i_sub_list.pop()
        use_list = modify_cpu_info_list(cpu_list) * 2
    elif len(cpu_list[0][0]) == 1:
        use_list = modify_cpu_info_list(cpu_list)
    # except Exception:
    #     # logger.debug("cpu_list error:{}".format(cpu_list))
    #     use_list = []
    return use_list


def bunch_use_cpu_list(list_procset, cpu_info_list, use_cpu_info_list):
    if list_procset == 'all' or list_procset == 'allcores':
        use_cpu_list = T_cpu_info_list(use_cpu_info_list)
        use_cpu_list = sum(
            sorted(use_cpu_list, key=lambda x: x[0]), [])

    elif list_procset == 'allsocks':
        use_cpu_list = allsocks_cpu_info_list(cpu_info_list)

    return use_cpu_list


def scatter_use_cpu_list(list_procset, use_cpu_info_list, cpu_info_list):
    if list_procset == 'all':
        use_cpu_list = T_cpu_info_list(use_cpu_info_list)
        use_cpu_list = sum(use_cpu_list, [])
        use_cpu_list = use_cpu_list[::2]+use_cpu_list[1::2]
    elif list_procset == 'allcores':
        use_cpu_list = T_cpu_info_list(use_cpu_info_list)
        use_cpu_list = sum(use_cpu_list, [])
    elif list_procset == 'allsocks':
        use_cpu_list = allsocks_cpu_info_list(cpu_info_list)
    return use_cpu_list


def spread_use_cpu_list(list_procset, use_cpu_info_list, cpu_info_list):
    if list_procset == 'all':
        use_cpu_list = sum(sum(use_cpu_info_list, []), [])
    elif list_procset == 'allcores':
        use_cpu_list = sum(sum(use_cpu_info_list, []), [])
    elif list_procset == 'allsocks':
        use_cpu_list = allsocks_cpu_info_list(cpu_info_list)
    return use_cpu_list


def get_mpi_map_info(list_procset='all', list_map='bunch', cores_per_socket=8,
                     hyper_threading=True, sockets_per_node=2):
    affinity_env = {'I_MPI_PIN_PROCESSOR_LIST':
                    '{}:map={}'
                    .format(list_procset, list_map)}

    cpu_num_list, cpu_info_list = get_numinfo_list(
        sockets_per_node, cores_per_socket, hyper_threading)
    logger.debug("cpu_num_list={}".format(cpu_num_list))
    logger.debug("cpu_info_list={}".format(cpu_info_list))

    use_cpu_num_list, use_cpu_info_list = get_mpi_cpu_list(
        sockets_per_node, cores_per_socket, list_procset, hyper_threading)
    logger.debug("use_cpu_num_list={}".format(use_cpu_num_list))
    logger.debug("use_cpu_info_list={}".format(use_cpu_info_list))

    # cpu_num = processor_num = len(use_cpu_num_list)

    # try:
    if list_map == 'bunch':
        use_cpu_list = bunch_use_cpu_list(
            list_procset, cpu_info_list, use_cpu_info_list)

    elif list_map == 'scatter':
        use_cpu_list = scatter_use_cpu_list(
            list_procset, use_cpu_info_list, cpu_info_list)

    elif list_map == 'spread':
        use_cpu_list = spread_use_cpu_list(
            list_procset, use_cpu_info_list, cpu_info_list)

    if list_procset == 'allcores' and hyper_threading is True:
        use_cpu_list = use_cpu_list * 2

    logger.debug("use_cpu_list={}".format(use_cpu_list))
    pid_bind = {}
    for pid, cpu in enumerate(use_cpu_list):
        pid_bind[str(pid)] = str(cpu)
    # except ZeroDivisionError:
    #     logger.debug("WARNING: Invalid Equation ZeroDivisionError")
    #     pid_bind = {}
    logging.debug("pid_bind={}".format(pid_bind))

    return [affinity_env, cpu_info_list, pid_bind]
