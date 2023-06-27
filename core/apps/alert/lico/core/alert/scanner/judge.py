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

from ..models import Policy
from .base import Base


class Judge(Base):
    def __init__(self, datas, policy):
        super().__init__(policy)
        self._datas = datas

    def _gen_alarm_list(self, targets):
        if "index" in targets.columns:
            return targets.loc[:, ['node', 'index']]\
                .drop_duplicates().to_dict(orient='records')
        else:
            return targets.loc[:, ['node']]\
                .drop_duplicates().to_dict(orient='records')

    def compare(self):
        if 'val' in self._datas.columns:
            if len(self._datas.val.to_list()) > 0:
                if self._aggregate == "max":
                    self._datas['val'] = self._datas['val'].astype(float)
                    df_max = self._datas.groupby('node').max().reset_index()
                    targets = df_max.loc[df_max.val <= self._val, :]
                    return self._gen_alarm_list(targets)
                elif self._aggregate == "min":
                    self._datas['val'] = self._datas['val'].astype(float)
                    df_min = self._datas.groupby('node').min().reset_index()
                    targets = df_min.loc[df_min.val >= self._val, :]
                    return self._gen_alarm_list(targets)
                else:
                    if self._policy.metric_policy == Policy.NODE_ACTIVE or \
                            self._policy.metric_policy == Policy.HARDWARE:
                        targets = self._datas.loc[:, ['node', 'val']]\
                            .drop_duplicates()
                        targets['val'] = targets.apply(
                            lambda x: self.get_health(x.val), axis=1
                        )
                        val_set = set(targets.val.to_list())
                        normal_set = {'on', 'ok', 'null'}
                        df_alert = targets[targets['val'].isin(
                            val_set.difference(normal_set)
                        )]
                        return self._gen_alarm_list(df_alert)
                    elif self._policy.metric_policy == \
                            Policy.HARDWARE_DISCOVERY:
                        targets = self._datas.loc[:, ['node', 'val']] \
                            .drop_duplicates()
                        val_set = set(targets.val.to_list())
                        normal_set = {'on', 'ok', 'null'}
                        df_alert = targets[targets['val'].isin(
                            val_set.difference(normal_set)
                        )]
                        return self._gen_alarm_list(df_alert)

        return []

    @staticmethod
    def get_health(health):
        import json
        try:
            return json.loads(
                health
            ).get('health', 'null')
        except Exception:
            return health
