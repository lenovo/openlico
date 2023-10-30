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
import glob
import logging
import os

from django.conf import settings
from django.db.transaction import atomic
from rest_framework.response import Response

from lico.core.contrib.exceptions import LicoInternalError
from lico.core.contrib.schema import json_schema_validate
from lico.core.contrib.views import APIView
from lico.core.job.base.job_state import JobState
from lico.core.job.models import Job
from lico.core.template.models import Module

from ..exceptions import (
    UserModuleDeleteFailed, UserModuleException, UserModulePermissionDenied,
)
from ..models import UserModuleJob
from ..utils import (
    MODULE_FILE_DIR, EasyBuildUtils, EasyConfigParser, UserModuleJobHelper,
    get_fs_operator, get_private_module,
)

logger = logging.getLogger(__name__)


class ModuleListView(APIView):
    def get(self, request):
        filter_type = request.query_params.get("type", "")
        self.user = request.user

        if filter_type == "public":
            ret = self.get_public_modules()
        elif filter_type == "private":
            ret = self.get_private_modules()
        else:
            ret = self.get_public_modules()
            ret.extend(self.get_private_modules())

        return Response(ret)

    def get_public_modules(self):
        return [
            {
                "name": module.name,
                "items": [
                    {
                        "name": item.name,
                        "version": item.version,
                        "path": item.path,
                        "category": item.category,
                        "description": item.description,
                        "parents": item.parents_list,
                        "location": item.location,
                        "type": "public"
                    }
                    for item in module.items.iterator()
                ],
                "type": "public"
            }
            for module in Module.objects.order_by(
                "name"
            ).iterator()
        ]

    def get_private_modules(self):
        spider = os.path.join(settings.TEMPLATE.LMOD_DIR, "spider")
        modules = []
        try:
            modules = get_private_module(spider, self.user)
        except Exception as e:
            logger.exception(e)
            raise LicoInternalError
        return modules

    @json_schema_validate({
        "type": "object",
        "properties": {
            "fullname": {
                "type": "string",
                "minimum": 1,
            },
        },
        "required": [
            "fullname"
        ]
    }, is_get=True)
    def delete(self, request):
        module_name = request.query_params.get('fullname')

        eb_utils = EasyBuildUtils(request.user)
        modulefile_path = eb_utils.get_eb_module_file_path(module_name)
        software_path = eb_utils.get_eb_software_path(module_name)

        try:
            # delete software
            self.delete_path(request.user, software_path)

            # delete modelefile
            self.delete_path(request.user, modulefile_path)
        except UserModulePermissionDenied as e:
            logger.exception(e)
            raise UserModuleDeleteFailed
        except Exception as e:
            logger.exception(e)
            raise LicoInternalError

        # remove module dir when module dir empty
        try:
            if len(os.listdir(os.path.dirname(software_path))) == 0:
                self.delete_path(request.user, os.path.dirname(software_path))
        except Exception as e:
            logger.exception(e)
        try:
            if len(os.listdir(os.path.dirname(modulefile_path))) == 0:
                self.delete_path(
                    request.user, os.path.dirname(modulefile_path))
        except Exception as e:
            logger.exception(e)

        return Response({
            "status": "ok"
        })

    def delete_path(self, user, path):
        fopr = get_fs_operator(user)
        if not fopr.path_exists(path):
            return
        if not fopr.path_iswriteable(
                fopr.path_dirname(path), user.uid, user.gid):
            raise UserModulePermissionDenied
        if fopr.path_isfile(path):
            fopr.remove(path)
        elif fopr.path_isdir(path):
            fopr.rmtree(path)


class UserModuleSubmitView(APIView):
    """
    Used for submitting usermodule related jobs.
    After gathering the parameters, it will send a request to `SubmitJobView`.
    """
    @json_schema_validate({
        "type": "object",
        "properties": {
            "easyconfig_path": {
                "type": "string",
                "minimum": 1
            },
            "job_queue": {
                "type": "string"
            },
            "template_id": {
                "type": "string"
            },
            "cores_per_node": {
                "type": "integer",
                "minimum": 1,
                "maximum": 999
            },
        },
        "required": [
            "easyconfig_path", "job_queue", "template_id"
        ]
    })
    @atomic
    def post(self, request):
        self.user = request.user
        data = request.data
        ret = self._request_job_proxy(data)
        return Response(ret)

    def _prepare_param(self, data):
        param = dict()
        param.update(data)
        eb_path = data["easyconfig_path"]
        param["software_name"] = os.path.splitext(os.path.basename(eb_path))[0]
        # Make sure job_name length is not greater than 64 digits,
        # in order to meet `SubmitJobView` API requirement.
        param["job_name"] = param["software_name"][:64]
        param["job_workspace"] = os.path.join(
            self.user.workspace, settings.USERMODULE.JOB_WORKSPACE
        )
        param["module_file_dir"] = MODULE_FILE_DIR

        return param

    def _request_job_proxy(self, data):
        helper = UserModuleJobHelper(self.user.username)
        param = self._prepare_param(data)
        try:
            ret = helper.submit_module_job(data["template_id"], param)
            job_id = ret['id']
            job = helper.query_job(job_id)

            # Create record for usermodule jobs
            log_path_glob = ""
            if job["scheduler_id"]:
                log_name_glob = "-".join([
                    param["job_name"], settings.LICO.SCHEDULER,
                    job["scheduler_id"]
                ]) + "*.log"
                log_path_glob = os.path.join(
                    param["job_workspace"], "easybuildlog", log_name_glob
                )
            UserModuleJob.objects.create(
                job_id=job_id,
                user=job["submitter"],
                software_name=param["software_name"],
                log_path=log_path_glob
            )

            ret.update(job)
            return ret
        except Exception as e:
            logger.exception(e)
            raise LicoInternalError from e


class UserModuleSearchView(APIView):
    def get(self, request, option):
        eb_utils = EasyBuildUtils(request.user)
        param = request.query_params.get('param', '')
        if option == "alnum":
            eb_configs = eb_utils.get_eb_configs(param=param)
        elif option == "name":
            eb_configs = eb_utils.get_eb_configs(param=param, is_alnum=False)
        else:
            raise NotImplementedError

        eb_data = list()
        for config in eb_configs:
            if not config or not config.endswith("eb"):
                continue
            if os.path.exists(config):
                try:
                    with open(config, 'r') as f:
                        module_info = EasyConfigParser(f.name, f.read()).\
                            parse()
                        module_info["easyconfig_path"] = config
                        eb_data.append(module_info)
                except Exception as e:
                    logger.exception(e)
                    raise UserModuleException

        return Response(eb_data)


class UserModuleBuildingView(APIView):
    def get_id_um_job_mapping(self, um_jobs):
        ret = {}
        for e in um_jobs:
            ret[e.job_id] = e
        return ret

    def extract_values(self, jobs, um_jobs_map):
        job_filter = [
            "scheduler_id", "job_name", "state", "operate_state",
            "scheduler_state"
        ]
        ret = []
        for job in jobs:
            job_id = job.id
            if job_id in um_jobs_map.keys():
                job_dict = job.as_dict(include=job_filter)
                job_dict.update(um_jobs_map[job_id].as_dict())
                ret.append(job_dict)
        return ret

    def get(self, request):
        submitter = request.user.username

        unfinished_jobs = Job.objects.filter(
            delete_flag=False, submitter=submitter,
            # job states: R, S, Q, H
            state__in=JobState.get_waiting_state_values()
        )
        unfinished_job_ids = unfinished_jobs.values_list("id", flat=True)
        unfinished_um_jobs = UserModuleJob.objects.filter(
            user=submitter, is_cleared=False, job_id__in=unfinished_job_ids
        )
        unfinished_um_map = self.get_id_um_job_mapping(unfinished_um_jobs)
        unfinished = self.extract_values(unfinished_jobs, unfinished_um_map)

        finished_um_jobs = UserModuleJob.objects.filter(
            user=submitter, is_cleared=False
        ).exclude(job_id__in=unfinished_job_ids).order_by("-update_time")[:10]
        finished_um_map = self.get_id_um_job_mapping(finished_um_jobs)

        finished_um_jids = finished_um_jobs.values_list("job_id", flat=True)
        finished = []
        if finished_um_jids:
            finished_jobs = Job.objects.filter(
                delete_flag=False, submitter=submitter,
                id__in=list(finished_um_jids)
            ).order_by("-update_time")
            finished = self.extract_values(finished_jobs, finished_um_map)

        ret = unfinished + finished
        return Response(ret)


class UserModuleJobView(APIView):
    def get_user_job_pair_by_id(self, um_id, username):
        # Return (UserModuleJob, Job) pair.
        um_job = UserModuleJob.objects.\
            filter(id=um_id, is_cleared=False).first()
        job = None
        if um_job:
            job = Job.objects.filter(
                submitter=username, id=um_job.job_id
            ).first()
        return (um_job, job)

    def get(self, request, pk):
        # View log, pk refers to UserModuleJob.id
        um_job, job = self.get_user_job_pair_by_id(pk, request.user.username)
        log = ""
        if job:
            log = um_job.log_path
            if job.scheduler_id in log and '*' in log:
                path_list = glob.glob(log)
                log = path_list[0] if path_list else log
                um_job.log_path = log
                um_job.save()
        else:
            raise Job.DoesNotExist
        return Response(dict(log_path=log))

    def put(self, request, pk):
        # Cancel, pk refers to UserModuleJob.id
        um_job, job = self.get_user_job_pair_by_id(pk, request.user.username)
        if job:
            helper = UserModuleJobHelper(request.user.username)
            helper.cancel_job(job.id)
        else:
            raise Job.DoesNotExist
        return Response()

    def delete(self, request, pk):
        # Clear, pk refers to UserModuleJob.id
        um_job, job = self.get_user_job_pair_by_id(pk, request.user.username)
        if um_job:
            um_job.is_cleared = True
            um_job.save()
        return Response()
