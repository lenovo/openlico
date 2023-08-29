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
import shutil
import time
import traceback
from datetime import datetime

import requests
import urllib3
from django.conf import settings
from django.http import FileResponse
from rest_framework.response import Response

from lico.core.contrib.client import Client
from lico.core.contrib.schema import json_schema_validate
from lico.core.contrib.views import APIView

from ..exceptions import (
    NotAFileException, PathNotExistException, PermissionDeniedException,
    ReportDownloadException, VtuneFailedException, VtuneTimeOutException,
)
from ..models.vtune import VtuneProfileWebPortal
from ..utils.vtune import (
    get_path_data, get_vtune_web_url, have_permission, submit_vtune_job,
)

logger = logging.getLogger(__name__)


class AnalyzerView(APIView):

    def get(self, request, job_id):
        data = dict()
        data["dir_path"] = []
        data["report_path"] = []
        data["command"] = ""
        data["show"] = False
        username = request.user.username
        logger.debug('>>>: username = {} '.format(username))
        template_client = Client().template_client(username=username)
        template_job = template_client.query_template_job(job_id=job_id)

        logger.debug('>>>: template_job = {} '.format(template_job))
        if template_job:
            job_parameters = json.loads(
                template_job['json_body']).get("parameters")
            intel_analyzer = job_parameters.get("intel_analyzer")
            logger.debug('>>>: intel_analyzer = {} '.format(intel_analyzer))
            logger.debug('>>>: intel_analyzer type = {} '.format(
                type(intel_analyzer)))
            data = get_path_data(job_id, username, intel_analyzer, data)
            vtune_analysis_type = job_parameters.get("vtune_analysis_type")
            if data["report_path"]:
                data["show"] = True
            elif data["dir_path"] and intel_analyzer == "vtune_profiler" and \
                    vtune_analysis_type == "platform-profiler":
                data["show"] = True
        logger.debug('>>>: data = {}'.format(data))
        return Response(data)


class AnalyzerReportView(APIView):
    permission_classes = ()

    def get(self, request):
        file_name = request.query_params.get("report", "")
        job_id = request.query_params.get('id', '')
        job_client = Client().job_client()
        job = job_client.query_job(job_id)
        workspace = job['workspace']
        scheduler_id = job['scheduler_id']
        file_path = os.path.join(
            workspace, "Intel_Analyzer_Results_" + str(scheduler_id),
            file_name)

        try:
            return FileResponse(open(file_path, 'rb'),
                                content_type='text/html')
        except IOError:
            raise PathNotExistException
        except Exception:
            raise NotAFileException

    def delete(self, request):
        path_list = request.data.get("path_list", "")
        status = ""
        for path in path_list:
            if not os.path.exists(path):
                raise PathNotExistException
            if not have_permission(request.user.username, path):
                raise PermissionDeniedException
            try:
                if os.path.isfile(path):
                    os.remove(path)
                else:
                    shutil.rmtree(path)
                status = "success"
            except Exception:
                status = "fail"
                break
        return Response({"status": status})


class AnalyzerReportDownloadView(APIView):

    def get(self, request):
        file_path = request.query_params.get("file_path", "")
        if not have_permission(request.user.username, file_path):
            raise PermissionDeniedException
        try:
            return FileResponse(open(file_path, 'rb'),
                                filename=file_path,
                                content_type='application/octet-stream',
                                as_attachment=True)
        except IOError:
            raise PathNotExistException
        except Exception:
            raise ReportDownloadException


class VTuneView(APIView):
    @json_schema_validate({
        "type": "object",
        "properties": {
            "job_template_ex_id": {"type": "number"},
            "data_directory": {"type": "string"},
            "platform_id": {"type": "number"},
        },
        "required": []
    })
    def post(self, request):
        job_template_ex_id = request.data.get("job_template_ex_id", None)
        data_directory = request.data.get("data_directory", None)
        platform_id = request.data.get("platform_id", None)
        username = request.user.username
        redirect_url = ''
        is_have_work_load_job = False
        client = Client().job_client(username=username)
        if job_template_ex_id:
            vtune_job = VtuneProfileWebPortal.objects.filter(
                work_load_job_id=job_template_ex_id)
        else:
            vtune_job = VtuneProfileWebPortal.objects.filter(
                work_load_platform_id=platform_id)

        if vtune_job:
            for job in vtune_job:
                try:
                    job_info = client.query_job(job.vtune_job_id)
                except Exception:
                    logger.error(traceback.format_exc())
                else:
                    if job_info['state'] in ('R', 'Q') and \
                            job_info['operate_state'] == 'created':
                        is_have_work_load_job = True
                        redirect_url = get_vtune_web_url(job_info)

        if not is_have_work_load_job:
            vtune_job = submit_vtune_job(
                job_template_ex_id, username, data_directory, platform_id)
            job_id = vtune_job["id"]
            if job_template_ex_id:
                VtuneProfileWebPortal.objects.create(
                    vtune_job_id=job_id,
                    work_load_job_id=job_template_ex_id,
                    username=username,
                )
            else:
                VtuneProfileWebPortal.objects.create(
                    vtune_job_id=job_id,
                    work_load_platform_id=platform_id,
                    username=username,
                )

            redirect_url = self.get_url_from_new_job(request, client, job_id)

        return Response({"redirect_url": redirect_url})

    def get_url_from_new_job(self, request, client, job_id):
        start_time = datetime.now()
        while True:
            job_info = client.query_job(job_id)
            redirect_url = get_vtune_web_url(job_info)
            if job_info['state'] == 'R' and redirect_url:
                host = request.META["HTTP_HOST"]
                url = "https://" + host + redirect_url
                urllib3.disable_warnings()
                req_times = 0
                session = requests.Session()
                while req_times < 5:
                    try:
                        result = session.get(url=url, verify=False, timeout=1)
                    except requests.exceptions.RequestException:
                        req_times += 1
                        continue
                    else:
                        if result.status_code == 200:
                            break
                if req_times < 5:
                    break
                else:
                    logger.error(">>>: Retry times have been used up and "
                                 "the request still time out")
                    raise VtuneTimeOutException
            elif (datetime.now() - start_time).seconds > \
                    settings.ONEAPI.VTUNE_RUNNING_TIMEOUT_SECONDS:
                if job_info['state'] == 'Q':
                    logger.error(">>>: Queue time out error, "
                                 "job status:{}".format(job_info['state']))
                    client.cancel_job(job_id)
                    raise VtuneTimeOutException
                else:
                    logger.error(">>>: Vtune failed error,"
                                 "job status:{}".format(job_info['state']))
                    raise VtuneFailedException
            time.sleep(2)
        return redirect_url
