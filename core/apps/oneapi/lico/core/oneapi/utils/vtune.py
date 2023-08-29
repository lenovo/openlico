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

import json
import logging
import os
import socket

from lico.core.contrib.base64 import encode_base64url
from lico.core.contrib.client import Client
from lico.core.template.exceptions import JobFileNotExist

from .common import make_hash

logger = logging.getLogger(__name__)


def get_vtune_web_url(job_info):
    port = 0
    redirect_url = ""
    for csres in job_info['job_csres']:
        if csres['csres_code'] == 'port':
            port = int(csres['csres_value'])
            break
    if port:
        if job_info['job_running']:
            base_url = encode_base64url("{}:{}".format(
                socket.gethostbyname(
                    job_info['job_running'][0]['hosts'].split(",")[0]),
                port).encode()).decode()
            redirect_url = "/dev/vtune/" + base_url + "/"
    return redirect_url


def submit_vtune_job(job_template_ex_id, username, data_directory,
                     platform_id):
    client = Client().template_client(username=username)
    if job_template_ex_id:
        try:
            template_job = client.query_template_job(job_id=job_template_ex_id)
            logger.debug('>>>: pre_template_job= {}'.format(template_job))
            template_job_body = json.loads(template_job['json_body'])
            logger.debug(
                '>>>: template_job_json_body = {}'.format(template_job_body))
            template_job_param = template_job_body['parameters']
            logger.debug(
                '>>>: template_job_parameters = {}'.format(template_job_param))
            params = {
                'job_name': 'VTune_for_' + template_job_param['job_name'],
                'job_workspace': template_job_param['job_workspace'],
                'job_queue': template_job_param['job_queue'],
                'runtime_id': template_job_param['runtime_id'],
                'data_directory': data_directory,
                'nodes': 1,
                'cores_per_node': 1,
                'ram_size': template_job_param['ram_size'],
                'run_time': "2h"
            }
        except Exception:
            raise JobFileNotExist
    else:
        try:
            from lico.core.platformanalysis.exceptions import (
                PlatformAnalysisRecordNotExist,
            )
            from lico.core.platformanalysis.models.vtune import (
                PlatformAnalysis,
            )
            from lico.core.template.models import Runtime
            job_client = Client().job_client(username=username)
            platform_analysis = PlatformAnalysis.objects. \
                filter(id=platform_id).first()
            runtime = Runtime.objects.filter(
                username='').get(name="Intel_Performance_Analyzer")
            runtime_id = [runtime.id]
            result_path = platform_analysis.result_path
            user_result_path = result_path.replace(get_home_path(username),
                                                   "MyFolder")
            queues = [
                queue['name'] for queue in job_client.query_available_queues()
            ]
            params = {
                'job_name': "VTune_for_" + platform_analysis.name,
                'job_workspace': user_result_path,
                'job_queue': queues[0],
                'runtime_id': runtime_id,
                'data_directory': user_result_path,
                'nodes': 1,
                'cores_per_node': 1,
                'ram_size': 0,
                'run_time': "2h"
            }
        except Exception:
            raise PlatformAnalysisRecordNotExist
    logger.debug('>>>: vtune_job_params = {}'.format(params))

    return client.submit_template_job('vtune', params)


def get_home_path(username):
    import pwd
    out = pwd.getpwnam(username)[5]
    logger.debug('-----home path is :{}----'.format(out))
    return out


def get_path_data(job_id, username, intel_analyzer, data):
    base_dir = "/Intel_Analyzer_Results"
    dir_map = {
        "aps": "{0}{1}_{3}/aps_{2}_{3}",
        "tac": "{0}{1}_{3}/itac_{2}_{3}.prot",
        "vtune_profiler": "{0}{1}_{3}/vtune_{2}_{3}",
        "advisor": "{0}{1}_{3}/advisor_survey_{2}_{3}"
    }
    report_map = {
        "aps": "{0}{1}_{3}/aps_{2}_{3}.html",
        "tac": "{0}{1}_{3}/itac_{2}_{3}.stf",
        "vtune_profiler": "{0}{1}_{3}/vtune_{2}_{3}.{4}.html",
        "advisor": "{0}{1}_{3}/advisor_survey_{2}_{3}.txt"
    }
    command_map = {
        "aps":
        "",
        "tac":
        "export LD_LIBRARY_PATH=/opt/intel/oneapi/itac/latest/bin/rtlib:"
        "/opt/intel/oneapi/installer/lib:$LD_LIBRARY_PATH \n"
        "traceanalyzer {0}{1}_{3}/itac_{2}_{3}.stf",
        "vtune_profiler":
        "vtune-backend --allow-remote-ui "
        "--enable-server-profiling "
        "--data-directory {0}{1}_{3}/vtune_{2}_{3}",
        "advisor":
        "advisor-gui {0}{1}_{3}/advisor_survey_{2}_{3}"
    }
    if intel_analyzer and intel_analyzer != "None":
        job_client = Client().job_client(username=username)
        job = job_client.query_job(job_id=job_id)
        logger.debug('>>>: job = {} '.format(job))
        if job:
            if intel_analyzer == "vtune_profiler":
                real_dir_sub = dir_map.get(intel_analyzer).format(
                    job["workspace"], base_dir, job["job_name"],
                    job["scheduler_id"])
                hash_dir_sub = make_hash(real_dir_sub)
                if os.path.exists(real_dir_sub):
                    data["dir_path"].append([real_dir_sub, hash_dir_sub])
                hosts_list = job["job_running"][0]["hosts"].split(",")
                for host in hosts_list:
                    real_report_sub = report_map.get(intel_analyzer).format(
                        job["workspace"], base_dir, job["job_name"],
                        job["scheduler_id"], host)
                    hash_report_sub = make_hash(real_report_sub)
                    if os.path.exists(real_report_sub):
                        data["report_path"].append(
                            [real_report_sub, hash_report_sub])
            else:
                real_dir_sub = dir_map.get(intel_analyzer).format(
                    job["workspace"], base_dir, job["job_name"],
                    job["scheduler_id"])
                hash_dir_sub = make_hash(real_dir_sub)
                if os.path.exists(real_dir_sub):
                    data["dir_path"].append([real_dir_sub, hash_dir_sub])
                real_report_sub = report_map.get(intel_analyzer).format(
                    job["workspace"], base_dir, job["job_name"],
                    job["scheduler_id"])
                hash_report_sub = make_hash(real_report_sub)
                if os.path.exists(real_report_sub):
                    data["report_path"].append(
                        [real_report_sub, hash_report_sub])

            data["command"] = command_map.get(intel_analyzer).format(
                job["workspace"], base_dir, job["job_name"],
                job["scheduler_id"])
    return data


def have_permission(username, path):
    path = os.path.abspath(path)

    for path_prefix in [
        "/tmp", "/var", get_home_path(username)  # nosec B108
    ]:
        if os.path.commonpath([
            path_prefix, path
        ]) == path_prefix:
            return True

    return False
