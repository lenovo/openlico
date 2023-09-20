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

import logging

from ..utils import get_hostnames_from_filter, parse_nodes_filter_from_db

logger = logging.getLogger(__name__)


class Base(object):
    def __init__(self, policy):
        self._policy = policy
        self._duration = int(self._policy.duration.total_seconds())
        self._aggregate, self._val = self._parse_portal()

    @property
    def _nodes(self):
        node_filter = parse_nodes_filter_from_db(self._policy.nodes)
        return get_hostnames_from_filter(node_filter)

    def _parse_portal(self):
        rep = ""
        val = 0.0
        method = ""
        try:
            portal = self._policy.portal
            if portal and (list(portal.keys())[0]).startswith('$'):
                rep, val = list(portal.items())[0]
            if rep == "$lt" or rep == "$lte":
                method = "max"
            elif rep == "$gt" or rep == "$gte":
                method = "min"
        except AttributeError:
            logger.exception("Portal {0} in policy {1} is unvalid."
                             .format(self._policy.portal,
                                     self._policy.metric_policy))
        return method, float(val)
