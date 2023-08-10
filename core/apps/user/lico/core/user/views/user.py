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
import re
from datetime import datetime

import attr
from dateutil.tz import tzutc
from django.conf import settings
from django.db import IntegrityError
from django.db.models import Case, CharField, F, Q, Value, When
from django.db.models.functions import Concat, Lower
from django.db.transaction import atomic
from django.http import StreamingHttpResponse
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from lico.core.contrib.eventlog import EventLog
from lico.core.contrib.permissions import AsAdminRole
from lico.core.contrib.schema import json_schema_validate
from lico.core.contrib.views import DataTableView, InternalAPIView

from ..database import DataBase
from ..exceptions import (
    GroupNotExists, InvalidGroup, InvalidLibuserOperation, InvalidOperation,
    InvalidUser, RemoveLastAdmin, RunningWorkExists, UserAlreadyExist,
    UserNotExists,
)
from ..libuser import Libuser
from ..models import ImportRecord, ImportRecordTask, User
from ..utils import create_import_records, require_libuser, users_billing_group
from . import APIView

logger = logging.getLogger(__name__)


class UserListView(InternalAPIView):
    def get(self, request):
        query = User.objects
        pattern = re.compile(r'^\d+(?:.\d+)?$')
        for key, value in request.query_params.items():
            if key in (
                'date_joined__lte', 'date_joined__gte',
                'date_joined__lt', 'date_joined__gt'
            ) and pattern.match(value):
                query = query.filter(
                    **{
                        key: datetime.fromtimestamp(float(value), tz=tzutc())
                    }
                )
        return Response(
            query.as_dict(
                include=['username', 'role', 'date_joined']
            )
        )


class UserDataTableView(DataTableView):
    def trans_result(self, result):
        user_dict = result.as_dict(
            inspect_related=False
        )
        user_dict["full_name"] = User.get_full_name(
            user_dict["first_name"], user_dict["last_name"]
        )
        user_dict["is_locked"] = not result.is_activate
        return user_dict

    def get_query(self, request, *args, **kwargs):
        param_args = json.loads(request.query_params["args"])
        query = User.objects
        if (
            param_args.get('sort', {}).get('prop', '') != "full_name" and
            "full_name" not in param_args.get('search', {}).get('props', [])
        ):
            return query

        return query.annotate(full_name=Case(
            When(first_name='', then=Lower(F('last_name'))),
            When(first_name=None, then=Lower(F('last_name'))),
            When(last_name='', then=Lower(F('first_name'))),
            When(last_name=None, then=Lower(F('first_name'))),
            default=Lower(
                Concat(F('first_name'), Value(' '), F('last_name'))
            ),
            output_field=CharField(),
        ))

    def global_search(self, query, param_args):
        if "search" not in param_args:
            return query

        filters = Q()
        for prop in param_args['search']['props']:
            if prop != "full_name":
                prop += '_lower'
                # icontains is not case-insensitive for some reason so we need
                # to adnotate for case-insensitive search
                query = query.annotate(
                    **{prop: Lower(F(prop[:-6]))}
                )
            prop += '__icontains'
            filters |= Q(
                **{prop: param_args['search']['keyword'].lower()}
            )
        query = query.filter(filters)
        return query

    @json_schema_validate({
        'type': 'object',
        'properties': {
            'group': {
                'type': 'string',
                'minLength': 1
            },
            'username': {
                'type': 'string',
                'minLength': 1
            },
            'password': {
                'type': 'string',
                'minLength': 1
            },
            'role': {
                'enum': list(User.ROLES.keys())
            },
            'first_name': {
                'type': 'string'
            },
            'last_name': {
                'type': 'string'
            },
            'email': {
                'type': 'string',
            }
        },
        'required': ['group', 'username', 'password', 'role']
    })
    @AsAdminRole
    @require_libuser
    @atomic
    def post(self, request):
        data = request.data
        try:
            user = DataBase().add_user(
                username=data["username"],
                role=data["role"],
                email=data.get("email"),
                first_name=data.get("first_name"),
                last_name=data.get("last_name")
            )
            Libuser().add_user(
                name=data["username"],
                password=data["password"],
                group=data["group"]
            )
            EventLog.opt_create(
                request.user.username, EventLog.user, EventLog.create,
                EventLog.make_list(user.id, user.username)
            )
            return Response()
        except IntegrityError as e:
            raise UserAlreadyExist from e
        except RuntimeError as e:
            raise UserAlreadyExist(
                "User already exist in Ldap"
            ) from e

    @json_schema_validate({
        'type': 'object',
        'properties': {
            'username': {
                'type': 'string',
                'minLength': 1
            },
            'role': {
                'enum': list(User.ROLES.keys())
            },
            'email': {
                'type': 'string',
            },
            'first_name': {
                'type': 'string',
            },
            'last_name': {
                'type': 'string',
            },
        },
        'required': ['username', 'role']
    })
    @AsAdminRole
    def put(self, request):
        import pwd
        data = request.data
        try:
            pwd.getpwnam(data["username"])
        except KeyError as e:
            raise UserNotExists from e
        try:
            user = DataBase().add_user(
                username=data["username"],
                role=data["role"],
                email=data.get("email"),
                first_name=data.get("first_name"),
                last_name=data.get("last_name")
            )
            EventLog.opt_create(
                request.user.username, EventLog.user, EventLog.create,
                EventLog.make_list(user.id, user.username)
            )
            return Response()
        except IntegrityError as e:
            raise UserAlreadyExist from e


class UserDetailView(APIView):

    @staticmethod
    def _is_other_admin(request, user):
        if user.is_admin and \
                user.username != request.user.username:
            raise PermissionDenied(
                "Unable to modify other admin information."
            )

    @staticmethod
    def _is_user_self(request, user):
        if not request.user.is_admin and \
                user.username != request.user.username:
            raise PermissionDenied(
                "Unable to modify other user information."
            )

    def get(self, request, pk):
        user = DataBase().get_user(pk)
        user_dict = user.as_dict(
            inspect_related=False
        )
        user_dict.update(
            is_admin=user.is_admin,
            is_activate=user.is_activate,
            full_name=User.get_full_name(
                user_dict["first_name"], user_dict["last_name"]
            ),
        )

        from lico.core.contrib.client import Client
        client = Client().auth_client()
        passwd = client.fetch_passwd(
            username=user.username, raise_exc=False
        )
        user_dict.update(
            **attr.asdict(
                passwd, filter=lambda attr, value: not (
                    attr.name.startswith('_') or attr.name == 'username'
                )
            )
        )
        return Response(user_dict)

    @AsAdminRole
    @atomic
    def delete(self, request, pk):
        try:
            delete_user = DataBase().get_user(pk, lock=True)
        except User.DoesNotExist:
            return Response()
        delete_user_username = delete_user.username
        self._is_other_admin(request, delete_user)
        if DataBase().is_last_admin(pk=pk):
            raise RemoveLastAdmin
        if settings.USER.USE_LIBUSER:
            try:
                Libuser().remove_user(delete_user_username)
            except InvalidOperation as e:
                raise InvalidLibuserOperation from e
        delete_user_id = delete_user.id
        delete_user.delete()
        EventLog.opt_create(
            request.user.username, EventLog.user, EventLog.delete,
            EventLog.make_list(delete_user_id, delete_user_username)
        )
        return Response()

    @json_schema_validate({
        'type': 'object',
        'properties': {
            'role': {
                'enum': list(User.ROLES.keys())
            },
            'email': {
                'type': 'string',
            },
            'last_name': {
                'type': 'string'
            },
            'first_name': {
                'type': 'string'
            },
            'group': {
                'type': 'string'
            },
        }
    })
    @atomic
    def patch(self, request, pk):
        other_user = DataBase().get_user(pk, lock=True)
        self._is_other_admin(request, other_user)
        self._is_user_self(request, other_user)

        # Only admin can modify role info
        if 'role' in request.data and \
                not request.user.is_admin and \
                request.data['role'] != request.user.role:
            raise PermissionDenied(
                "Unable to modify role information."
            )

        data = request.data
        DataBase().update_user(pk=pk, data=data)

        # Only admin can modify group info
        if 'group' in data and \
                request.user.is_admin:
            try:
                Libuser().modify_user_group(
                    other_user.username, data['group']
                )
            except InvalidOperation as e:
                raise InvalidLibuserOperation from e
            except InvalidUser as e:
                raise UserNotExists from e
            except InvalidGroup as e:
                raise GroupNotExists from e
        EventLog.opt_create(
            request.user.username, EventLog.user, EventLog.update,
            EventLog.make_list(other_user.id, other_user.username)
        )
        return Response(
            DataBase().get_user(pk).as_dict(
                inspect_related=False
            )
        )


class UserExportView(APIView):

    def get(self, request):
        from django.template.loader import render_to_string
        export_file_name = "export_user_{0:%Y%m%d%H%M%S}.csv".format(
            timezone.now()
        )
        users_bill_group = users_billing_group()

        user_info = render_to_string(
            "user/export.csv",
            context={
                "users": User.objects.all(),
                "users_bill_group": users_bill_group
            }
        )
        response = StreamingHttpResponse(
            user_info, charset=request.query_params.get('charset')
        )
        response['Content-Type'] = 'application/octet-stream'
        response['Content-Disposition'] = \
            f'attachment;filename={export_file_name}'
        return response


class UserImportDetailView(DataTableView):
    permission_classes = (AsAdminRole, )

    columns_mapping = {
        'row': 'row',
        'username': 'username',
        'role': 'role',
        'last_name': 'last_name',
        'first_name': 'first_name',
        'email': 'email',
        'ret': 'ret',
    }

    def trans_result(self, result):
        return result.as_dict(
            inspect_related=False
        )

    def get_query(self, request, *args, **kwargs):
        task = ImportRecordTask.objects.get(
            owner=request.user.username
        )
        return ImportRecord.objects.filter(
            task=task).order_by('row')


class UserImportView(APIView):

    @AsAdminRole
    def post(self, request):
        from ..tasks import import_record_task
        current_user = request.user.username
        up_file = request.FILES.get('upload')
        with atomic():
            try:
                exists_task = ImportRecordTask.objects.select_for_update(
                ).get(owner=current_user)
                if exists_task.is_running:
                    logger.exception("Running work exists")
                    raise RunningWorkExists
                else:
                    exists_task.delete()
            except ImportRecordTask.DoesNotExist:
                logger.info("No worker under the current user")
            task = ImportRecordTask.objects.create(owner=current_user)
            create_import_records(up_file, task)
        import_record_task.delay(task.id, current_user)
        return Response()

    @AsAdminRole
    @atomic
    def delete(self, request):
        current_user = request.user.username
        try:
            owner_task = ImportRecordTask.objects.get(
                owner=current_user, is_running=True
            )
        except ImportRecordTask.DoesNotExist:
            logger.info("No corresponding worker or worker completed")
            return Response()
        owner_task.is_running = False
        owner_task.save()
        return Response()

    @AsAdminRole
    def get(self, request):
        current_user = request.user.username
        try:
            task = ImportRecordTask.objects.get(owner=current_user)
        except ImportRecordTask.DoesNotExist:
            logger.info("No import record found under current user")
            return Response({
                "status": "idle"
            })
        if task.is_running:
            return Response({
                "status": "importing",
                "progress": {
                    "total": task.records.count(),
                    "finished": task.records.filter(ret__isnull=False).count(),
                    "success": task.records.filter(ret=True).count()
                }
            })
        else:
            return Response({
                "status": "idle",
                "last_importing": {
                    "total": task.records.count(),
                    "finished": task.records.filter(ret__isnull=False).count(),
                    "success": task.records.filter(ret=True).count(),
                    "finish_time": int(task.update_time.timestamp())
                }
            })
