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

from django.db import transaction
from django.db.models import Case, IntegerField, Q, When
from django.db.models.functions import Cast
from django.db.transaction import atomic
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from lico.client.contrib.exception import Unauthorized
from lico.core.contrib.authentication import (
    RemoteApiKeyAuthentication, RemoteJWTInternalAuthentication,
    RemoteJWTWebAuthentication,
)
from lico.core.contrib.eventlog import EventLog
from lico.core.contrib.permissions import AsOperatorRole
from lico.core.contrib.schema import json_schema_validate
from lico.core.contrib.views import APIView, DataTableView, InternalAPIView
from lico.scheduler.base.exception.job_exception import (
    HoldJobFailedException, ReleaseJobFailedException,
)

from ..base.job_operate_state import JobOperateState
from ..base.job_state import JobState
from ..exceptions import (
    DeleteRunningJobException, HoldJobException, JobException,
    QueryJobDetailException, ReleaseJobException,
)
from ..helpers.scheduler_helper import (
    get_admin_scheduler, get_scheduler, parse_job_identity,
)
from ..models import Job
from ..utils import get_users_from_filter

logger = logging.getLogger(__name__)


class JobListView(DataTableView):
    columns_mapping = {  # <display field name>: <DB field name>
        'id': 'id',
        'scheduler_id': 'scheduler_id',
        'job_name': 'job_name',
        'queue': 'queue',
        'submit_time': 'submit_time',
        'start_time': 'start_time',
        'end_time': 'end_time',
        'submitter': 'submitter',
        'scheduler_state': 'scheduler_state',
        'state': 'state',
        'operate_state': 'operate_state',
        'tag': 'tags__name',
    }

    def get_job_query_set(self, user_role, request_role, submitter):
        query = Job.objects.filter(delete_flag=False)

        if 'admin' == request_role:
            if user_role < AsOperatorRole.floor:
                raise PermissionDenied
        else:
            query.filter(submitter=submitter)

        return query

    def get_query(self, request, *args, **kwargs):
        return self.get_job_query_set(
            user_role=request.user.role,
            request_role=request.query_params.get('role', None),
            submitter=request.user.username
        )

    def trans_result(self, result):
        return result.as_dict(exclude=['job_content', 'delete_flag'])

    def global_sort_fields(self, param_args):
        sort = param_args.get("sort")
        if sort and sort['prop'] in ['scheduler_id', 'priority']:
            sql = Case(
                When(Q(scheduler_id=''), then=-1),
                When(Q(priority=''), then=-9999),
                default=Cast(sort['prop'], IntegerField())
            )
            return [sql.asc() if sort['order'] == 'ascend' else sql.desc()]
        else:
            return super().global_sort_fields(param_args)

    def filters(self, query, filters):
        for field in filters:
            if field['prop'] == 'submitter':
                field['values'] = get_users_from_filter(
                    filter_=field,
                    ignore_non_lico_user=False
                )
                break
        return super().filters(query, filters).distinct()


class InternalJobView(InternalAPIView):

    def get(self, request, pk):
        job = Job.objects.get(id=pk)

        return Response(job.as_dict())


class JobView(APIView):
    authentication_classes = (
        RemoteJWTWebAuthentication,
        RemoteJWTInternalAuthentication,
        RemoteApiKeyAuthentication
    )

    def get_job_query_set(self, is_admin, submitter):
        query = Job.objects.filter(delete_flag=False)
        if not is_admin:
            query = query.filter(submitter=submitter)
        return query

    def get(self, request, pk):
        query = self.get_job_query_set(
            is_admin=request.user.is_admin,
            submitter=request.user.username
        )
        job = query.get(id=pk)
        return Response(
            job.as_dict(
                on_finished_options={
                    "password": "get_job_password",
                    "entrance_uri": "get_entrance_uri"
                }
            )
        )

    def put(self, request, pk):
        # Function Usage: cancel job
        operator = request.user
        job_operator_status = None

        try:
            with transaction.atomic():
                query = self.get_job_query_set(
                    is_admin=operator.is_admin,
                    submitter=operator.username
                )
                job = query.get(id=pk)
                if job.state in JobState.get_final_state_values() or \
                    job.operate_state in [
                    JobOperateState.CANCELLING.value,
                    JobOperateState.CREATING.value
                ]:
                    return Response({
                        "id": job.id,
                        "scheduler_id": job.scheduler_id,
                        "job_name": job.job_name,
                        "state": job.operate_state
                    })

                job_operator_status = job.operate_state
                job.operate_state = JobOperateState.CANCELLING.value
                job.save()

            if job.submitter == operator.username:
                scheduler = get_scheduler(operator)
            elif operator.is_admin:
                scheduler = get_admin_scheduler()
            else:
                raise Unauthorized

            scheduler.cancel_job(
                job_identity=parse_job_identity(job.identity_str)
            )
        except Exception as e:
            logger.exception("Cancel Job error.")
            if job_operator_status:
                with transaction.atomic():
                    job = Job.objects.get(id=pk)
                    job.operate_state = job_operator_status
                    job.save()
            raise JobException from e
        # add  operationlog
        EventLog.opt_create(
            operator.username, EventLog.job, EventLog.cancel,
            EventLog.make_list(pk, job.job_name)
        )
        return Response({
            "id": job.id,
            "scheduler_id": job.scheduler_id,
            "job_name": job.job_name,
            "state": JobOperateState.CANCELLING.value
        })

    def delete(self, request, pk):
        with transaction.atomic():
            try:
                job = Job.objects.filter(
                    submitter=request.user.username,
                    delete_flag=False
                ).get(id=pk)
            except Job.DoesNotExist:
                logger.warning(
                    "Delete job_id %s failed, job objects not exist.", pk
                )
                raise
            if job.state in JobState.get_waiting_state_values():
                raise DeleteRunningJobException

            job.delete_flag = True
            job.save()

        EventLog.opt_create(
            request.user.username, EventLog.job, EventLog.delete,
            EventLog.make_list(pk, job.job_name)
        )

        return Response({"job_name": job.job_name})


class JobRawInfoView(APIView):

    def get(self, request, pk):
        scheduler = get_scheduler(request.user)
        job = Job.objects.get(id=pk)
        try:
            ret = scheduler.query_job_raw_info(
                job_identity=parse_job_identity(job.identity_str)
            )
        except Exception as e:
            logger.exception("Query job raw info failed.")
            raise QueryJobDetailException from e
        return Response(ret)


class JobBaseActionView(APIView):
    @staticmethod
    def is_admin_or_operator(user, role):
        if role in ['admin', 'operator'] and \
                user.role >= AsOperatorRole.floor:
            return True
        return False

    @staticmethod
    def get_job_object(pk, user, has_manager_permission=False):
        job = Job.objects.get(id=pk, delete_flag=False)
        if has_manager_permission:
            return job
        if job.submitter != user.username:
            raise PermissionDenied
        return job

    @staticmethod
    def get_job_scheduler(user, has_manager_permission=False):
        if has_manager_permission:
            return get_admin_scheduler()
        else:
            return get_scheduler(user)

    @staticmethod
    def get_action_response(job, state):
        return {
            "id": job.id,
            "scheduler_id": job.scheduler_id,
            "job_name": job.job_name,
            "state": state
        }


class JobHoldView(JobBaseActionView):
    @json_schema_validate({
        "type": "object",
        "properties": {
            "job_id": {
                "type": "integer",
            },
            "role": {
                "type": "string",
                "enum": ["admin", "operator", "staff"],
            },
        },
        "required": ["job_id"]
    })
    @atomic()
    def post(self, request):
        user = request.user
        pk = request.data['job_id']
        role = request.data.get('role', None)
        try:
            has_manager_permission = self.is_admin_or_operator(user, role)
            job = self.get_job_object(pk, user, has_manager_permission)
            res = self.get_action_response(job, JobState.HOLD.value)
            if job.state == JobState.HOLD.value:
                return Response(res)
            if job.state != JobState.QUEUING.value:
                logger.exception('Only support hold queuing job, '
                                 'job state is: %s', job.state)
                raise HoldJobException
            scheduler = self.get_job_scheduler(user, has_manager_permission)
            scheduler.hold_job(
                job_identity=parse_job_identity(job.identity_str))
            return Response(res)
        except HoldJobFailedException:
            raise HoldJobException
        except Exception as e:
            logger.exception('Failed to hold the job, reason: %s' % e)
            raise HoldJobException


class JobReleaseView(JobBaseActionView):
    @json_schema_validate({
        "type": "object",
        "properties": {
            "job_id": {
                "type": "integer",
            },
            "role": {
                "type": "string",
                "enum": ["admin", "operator", "staff"],
            },
        },
        "required": ["job_id"]
    })
    @atomic()
    def post(self, request):
        user = request.user
        pk = request.data['job_id']
        role = request.data.get('role', None)
        try:
            has_manager_permission = self.is_admin_or_operator(user, role)
            job = self.get_job_object(pk, user, has_manager_permission)
            res = self.get_action_response(job, JobState.QUEUING.value)
            if job.state == JobState.QUEUING.value:
                return Response(res)
            if job.state != JobState.HOLD.value:
                logger.exception('Only support release held job, '
                                 'job state is: %s', job.state)
                raise ReleaseJobException
            scheduler = self.get_job_scheduler(user, has_manager_permission)
            scheduler.release_job(
                job_identity=parse_job_identity(job.identity_str))
            return Response(res)
        except ReleaseJobFailedException:
            raise ReleaseJobException
        except Exception as e:
            logger.exception('Failed to release the job, reason: %s' % e)
            raise ReleaseJobException
