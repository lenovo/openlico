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

from typing import Callable, Dict, Iterable, Optional

from django.db.models import Model as BaseModel
from django.db.models.manager import BaseManager
from django.db.models.query import QuerySet as BaseQuerySet


class ToDictMixin:
    as_dict_exclude = ()

    def as_dict(
        self, inspect_related=True,
        include: Optional[Iterable[str]] = None,
        exclude: Optional[Iterable[str]] = None,
        related_field_options: Optional[Dict] = None,
        **on_finished_options
    ):
        if include is not None:
            def is_excluded(field):
                return field not in include
        else:
            if exclude is None:
                exclude = set(self.as_dict_exclude)
            else:
                exclude = set(exclude) | set(self.as_dict_exclude)

            def is_excluded(field):
                return field in exclude

        if related_field_options is None:
            related_field_options = {}

        result = {}
        for field in self._meta.concrete_fields:
            if is_excluded(field.name) or field.is_relation:
                continue
            if hasattr(field, 'dict_from_object'):
                result[field.name] = field.dict_from_object(self)
            else:
                result[field.name] = field.value_from_object(self)

        if inspect_related:
            self.inspect_related_fields(
                result, is_excluded, related_field_options
            )

        self.as_dict_on_finished(result, is_excluded, **on_finished_options)

        return result

    def as_dict_on_finished(
        self, result: Dict, is_exlucded: Callable, **kwargs
    ):
        pass

    def inspect_related_fields(
        self, result: Dict, is_excluded: Callable,
        related_field_options: Dict
    ):
        related_fields = (
            rf for rf in self._meta.get_fields()
            if rf.is_relation and not is_excluded(rf.get_cache_name())
        )
        for rf in related_fields:
            option = related_field_options.get(
                rf.get_cache_name(), dict(inspect_related=False)
            )
            if rf.one_to_many:
                self._on_inspect_one_to_many_field(rf, result, option)
            if rf.many_to_one:
                self._on_inspect_many_to_one_field(rf, result, option)
            if rf.one_to_one:
                self._on_inspect_one_to_one_field(rf, result, option)
            if rf.many_to_many:
                self._on_inspect_many_to_many_field(rf, result, option)

    def _on_inspect_one_to_many_field(self, rf, result: Dict, option: Dict):
        cache_name = rf.get_cache_name()
        result[cache_name] = [
            related_object.as_dict(**option)
            for related_object in getattr(self, cache_name).iterator()
            if hasattr(related_object, 'as_dict')
        ]

    def _on_inspect_one_to_one_field(self, rf, result: Dict, option: Dict):
        cache_name = rf.get_cache_name()
        related_object = getattr(self, cache_name, None)
        if related_object is None:
            result[cache_name] = None
        if hasattr(related_object, 'as_dict'):
            result[cache_name] = related_object.as_dict(**option)

    def _on_inspect_many_to_one_field(self, rf, result: Dict, option: Dict):
        cache_name = rf.get_cache_name()
        related_object = getattr(self, cache_name, None)
        if related_object is None:
            result[cache_name] = None
        if hasattr(related_object, 'as_dict'):
            result[cache_name] = related_object.as_dict(**option)

    def _on_inspect_many_to_many_field(self, rf, result: Dict, option: Dict):
        cache_name = rf.get_cache_name()
        result[cache_name] = [
            related_object.as_dict(**option)
            for related_object in getattr(self, cache_name).iterator()
            if hasattr(related_object, 'as_dict')
        ]


class QuerySet(BaseQuerySet):
    def as_dict(self, *args, **kwargs):
        return [
            obj.as_dict(*args, **kwargs)
            for obj in self.iterator()
        ]

    def ci_search(self, **kwargs):
        # case insensitive search
        db_table_name = self.model._meta.db_table
        where_clause = ""
        for prop, keyword in kwargs.items():
            if where_clause:
                where_clause += " OR "
            keyword = keyword.replace("'", "\\'")
            where_clause += f"{db_table_name}.{prop} " \
                            f"LIKE '%%{keyword}%%' COLLATE utf8_general_ci"

        return self.extra(where=[where_clause])  # nosec

    def ci_exact(self, **kwargs):
        # query with case insensitive
        db_table_name = self.model._meta.db_table
        where_clause = ""
        for prop, keyword in kwargs.items():
            if where_clause:
                where_clause += " AND "
            where_clause += f"{db_table_name}.{prop}='{keyword}' " \
                f"COLLATE utf8_general_ci"
        return self.extra(where=[where_clause])  # nosec


class Manager(BaseManager.from_queryset(QuerySet)):
    pass


class Model(BaseModel, ToDictMixin):
    objects = Manager()

    class Meta:
        abstract = True

