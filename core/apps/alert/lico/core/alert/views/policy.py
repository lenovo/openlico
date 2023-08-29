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
from datetime import timedelta

from django.db import transaction
from django.db.utils import IntegrityError
from rest_framework.response import Response

from lico.core.contrib.eventlog import EventLog
from lico.core.contrib.permissions import AsAdminRole
from lico.core.contrib.schema import json_schema_validate
from lico.core.contrib.views import APIView

from ..exceptions import PolicyExistsException
from ..models import NotifyTarget, Policy
from ..utils import format_nodes_filter_to_db, parse_nodes_filter_from_db

logger = logging.getLogger(__name__)


class PolicyView(APIView):
    permission_classes = (AsAdminRole,)

    def get(self, request):
        return Response(
            Policy.objects.as_dict(
                inspect_related=False,
                include=['id', 'name', 'level', 'status']
            )
        )

    @json_schema_validate({
        "type": "object",
        "properties": {
            "name": {"type": "string"},  # policy_name
            "metric_policy": {"type": "string"},  # policy_metric
            "portal": {
                "type": "object",
                "properties": {
                    "gt": {"type": "number"}
                }
            },
            "duration": {"type": "integer", "minimum": 0},
            "nodes": {
                "type": "object",
                "properties": {
                    "value_type": {"type": "string"},
                    "values": {"type": "array"}
                }
            },
            "level": {"type": "string"},  # policy_level
            "targets": {  # policy_targets
                "type": "array",
                "items": {"type": "integer"}
            },
            "status": {"type": "string"},
            "language": {"type": "string"},
            "script": {"type": "string"},  # no
            "comments": {"type": "array"},
        },

        "required": ["name", "metric_policy", "portal", "duration", "level",
                     "targets", "status"]
    })
    @transaction.atomic
    def post(self, request):
        policy = Policy(
            metric_policy=request.data.get('metric_policy'),
            name=request.data.get('name'),
            portal=request.data.get('portal'),
            duration=timedelta(seconds=request.data.get('duration')),
            status=request.data.get('status'),
            level=request.data.get('level'),
            nodes=format_nodes_filter_to_db(request.data.get('nodes')),
            creator=request.user.username,
            script=request.data.get('script', ''),
            language=request.data.get('language', 'en'),
            comments=request.data.get('comments', [])
        )

        try:
            policy.save()
            query_s = NotifyTarget.objects.filter(
                id__in=request.data.get('targets', [])
            )
            policy.targets.set(query_s)
            policy.save()

            # add operationlog
            EventLog.opt_create(
                request.user.username,
                EventLog.policy,
                EventLog.create,
                EventLog.make_list(policy.id, policy.name)
            )

        except IntegrityError as e:
            logger.info(e, exc_info=True)
            raise PolicyExistsException from e
        return Response()


class PolicyDetailView(APIView):
    permission_classes = (AsAdminRole,)

    def get(self, request, pk):
        policy_obj = Policy.objects.get(id=pk)

        policy_as_dict = policy_obj.as_dict(
            exclude=["language", "create_time", "creator", "alert_set"]
        )
        policy_as_dict['duration'] = \
            policy_as_dict['duration'].total_seconds()
        policy_as_dict['nodes'] = \
            parse_nodes_filter_from_db(policy_as_dict['nodes'])
        policy_as_dict['targets'] = \
            [t['id'] for t in policy_as_dict['targets']]

        return Response(
            policy_as_dict
        )

    @json_schema_validate({
        "type": "object",
        "properties": {
            "name": {"type": "string"},  # policy_name
            "metric_policy": {"type": "string"},  # policy_metric
            "portal": {
                "type": "object",
                "properties": {
                    "gt": {"type": "number"}
                }
            },
            "duration": {"type": "integer", "minimum": 0},
            "nodes": {
                "type": "object",
                "properties": {
                    "value_type": {"type": "string"},
                    "values": {"type": "array"}
                }
            },
            "level": {"type": "string"},  # policy_level
            "targets": {  # policy_targets
                "type": "array",
                "items": {"type": "integer"}
            },
            "status": {"type": "string"},
            "language": {"type": "string"},
            "script": {"type": "string"},  # no
            "comments": {"type": "array"}
        },

        "required": ["name", "metric_policy", "portal", "duration", "level",
                     "targets", "status"]
    })
    @transaction.atomic
    def put(self, request, pk):
        policy = Policy.objects.select_for_update().get(pk=pk)
        old_policy_name = policy.name

        policy.metric_policy = request.data.get('metric_policy')
        policy.name = request.data.get('name')
        policy.portal = request.data.get('portal')
        policy.duration = timedelta(seconds=request.data.get('duration'))
        policy.status = request.data.get('status')
        policy.level = request.data.get('level')
        policy.nodes = format_nodes_filter_to_db(request.data.get('nodes'))
        policy.script = request.data.get('script', '')
        policy.language = request.data.get('language', 'en')
        policy.comments = request.data.get('comments', [])

        query_s = NotifyTarget.objects.filter(
            id__in=request.data.get('targets', [])
        )
        policy.targets.set(query_s)
        try:
            policy.save()

            # add operationlog
            EventLog.opt_create(
                request.user.username,
                EventLog.policy,
                EventLog.update,
                EventLog.make_list(pk, old_policy_name)
                                )
        except IntegrityError as e:
            logger.info(e, exc_info=True)
            raise PolicyExistsException from e
        return Response()

    @transaction.atomic
    def delete(self, request, pk):
        policy = Policy.objects.select_for_update().get(pk=pk)
        policy.delete()

        # add operationlog
        EventLog.opt_create(
            request.user.username,
            EventLog.policy,
            EventLog.delete,
            EventLog.make_list(pk, policy.name)
        )
        return Response()
