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

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.transaction import atomic

from lico.core.template.models import (
    Runtime, RuntimeEnv, RuntimeModule, RuntimeScript,
)


class Command(BaseCommand):
    help = 'Init or Update Runtime RuntimeEnv RuntimeScript RuntimeModule DB'

    def add_arguments(self, parser):
        parser.add_argument(
            '--init',
            help='init or update runtime db',
            action='store_true'
        )

    def handle(self, *args, **options):
        with atomic():
            if settings.ONEAPI.ENABLE:
                module_path = settings.ONEAPI.INTEL_MODULE_PATH
                runtime_dict = {
                    0: {
                        "runtime_name": "Intel_Extension_for_Tensorflow_CPU",
                        "runtime_script": "/setvars.sh",
                        "runtime_env": {
                            "CONDA_ENV": "tensorflow",
                            "KMP_BLOCKTIME": "0",
                            "KMP_SETTINGS": "1",
                            "KMP_AFFINITY":
                                "granularity=fine,verbose,compact,1,0"
                        },
                        "runtime_module": ""
                    },
                    1: {
                        "runtime_name": "Intel_Extension_for_Tensorflow_GPU",
                        "runtime_script": "/setvars.sh",
                        "runtime_env": {
                            "CONDA_ENV": "tensorflow-gpu"
                        },
                        "runtime_module": ""
                    },
                    2: {
                        "runtime_name": "Intel_Extension_for_PyTorch_CPU",
                        "runtime_script": "/setvars.sh",
                        "runtime_env": {
                            "CONDA_ENV": "pytorch"
                        },
                        "runtime_module": ""
                    },
                    3: {
                        "runtime_name": "Intel_Extension_for_PyTorch_GPU",
                        "runtime_script": "/setvars.sh",
                        "runtime_env": {
                            "CONDA_ENV": "pytorch-gpu"
                        },
                        "runtime_module": ""
                    },
                    4: {
                        "runtime_name": "Intel_oneAPI_Base_And_HPC_Toolkit",
                        "runtime_script": "/setvars.sh",
                        "runtime_env": "",
                        "runtime_module": ""
                    },
                    5: {
                        "runtime_name": "Intel_Performance_Analyzer",
                        "runtime_script": "",
                        "runtime_env": "",
                        "runtime_module": ["advisor/latest", "itac/latest",
                                           "vtune/latest"]
                    },
                    6: {
                        "runtime_name": "Intel_MPI",
                        "runtime_script": "",
                        "runtime_env": "",
                        "runtime_module": ["mpi/latest", "compiler-rt/latest"]
                    },
                    7: {
                        "runtime_name": "Intel_OpenMP",
                        "runtime_script": "",
                        "runtime_env": "",
                        "runtime_module": ["mpi/latest", "compiler-rt/latest"]
                    },
                    8: {
                        "runtime_name": "Intel_Distribution_for_Python",
                        "runtime_script": "/intelpython/latest/env/vars.sh",
                        "runtime_env": "",
                        "runtime_module": ""
                    },
                    9: {
                        "runtime_name": "Intel_Distribution_of_Modin",
                        "runtime_script": "/setvars.sh",
                        "runtime_env": {
                            "CONDA_ENV": "modin"
                        },
                        "runtime_module": ""
                    }
                }

                for index, dic in runtime_dict.items():
                    runtime_default = {
                        "name": dic["runtime_name"],
                        "tag": "sys:intel",
                        "type": "Runtime",
                        "username": "",
                    }

                    runtime_obj, created = Runtime.objects.update_or_create(
                        **runtime_default,
                        defaults=runtime_default
                    )

                    if runtime_obj:
                        if dic["runtime_script"] != "":
                            script_default = {
                                "filename":
                                    module_path + dic["runtime_script"],
                                "index": 0,
                                "runtime_id": runtime_obj.id
                            }

                            RuntimeScript.objects.update_or_create(
                                **script_default,
                                defaults=script_default
                            )

                        if isinstance(dic["runtime_env"], dict):
                            env_index = 0
                            for name, value in dic["runtime_env"].items():
                                env_default = {
                                    "name": name,
                                    "value": value,
                                    "runtime_id": runtime_obj.id,
                                    "index": env_index
                                }

                                RuntimeEnv.objects.update_or_create(
                                    **env_default,
                                    defaults=env_default
                                )
                                env_index += 1

                        if isinstance(dic["runtime_module"], list):
                            for i in range(len(dic["runtime_module"])):
                                module_default = {
                                    "module": dic["runtime_module"][i],
                                    "index": i,
                                    "runtime_id": runtime_obj.id
                                }

                                RuntimeModule.objects.update_or_create(
                                    **module_default,
                                    defaults=module_default
                                )

                if created:
                    print('Init oneAPI runtime success')
                else:
                    print('Update oneAPI runtime success')
            else:
                print('\033[0;33mWarning: Can not init oneAPI runtime '
                      'due to oneAPI is disabled\033[0m')
