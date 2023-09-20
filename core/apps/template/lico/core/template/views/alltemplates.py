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

import datetime
import json
import re
from collections import defaultdict
from itertools import chain

from django.db.models import Q
from django.db.models.aggregates import Count, Max
from django.utils import timezone
from pandas import DataFrame
from rest_framework.response import Response

from lico.core.contrib.schema import json_schema_validate
from lico.core.contrib.views import APIView, DataTableView

from ..models import FavoriteTemplate, Template, TemplateJob, UserTemplate


class CategoriesView(APIView):

    @json_schema_validate({
        "type": "object",
        "properties": {
            "feature_code": {
                "type": "string",
                "minLength": 1
            }
        }
    }, is_get=True)
    def get(self, request):
        username = request.user.username
        feture_code = request.query_params["feature_code"]
        user_template = UserTemplate.objects.filter(
            Q(type='public') | Q(username=username)
        )
        system_template = [
            template for template in Template.objects.filter(
                display=True
            ).iterator() if self.sync_templates(
                feture_code, template.feature_code
            )
        ]
        categories = self.get_categories(
            user_template, system_template
        )
        template_code = self.get_templates_code(
            user_template, system_template
        )
        return Response(
            {
                "categories": categories,
                "favorites": FavoriteTemplate.objects.filter(
                    username=username, code__in=template_code
                ).count(),
                "my_templates": UserTemplate.objects.filter(
                    username=username
                ).count()
            }
        )

    @staticmethod
    def sync_templates(feature_code, template_feature_code):
        '''
        :param feature_code: "lico,hpc,ai,oneapi,sc.host.slurm"
        :param template_feature_code: "sc.host.*,oneapi" | "hpc"
        :return: True | False
        '''
        return all(
            (
                re.search(code, feature_code)
                for code in template_feature_code.strip().split(",")
            )
        )

    @staticmethod
    def get_categories(user_templates, system_templates):
        template_categories = [
            template.category for template in chain(
                user_templates, system_templates
            )
        ]
        categories = defaultdict(int)
        categories["All"] = len(template_categories)
        all_categories = []
        for template_category in template_categories:
            all_categories += [
                tmp_category.strip()
                for tmp_category in template_category.strip().split(",")
            ]
        for category in all_categories:
            categories[category] += 1
        return dict(categories)

    @staticmethod
    def get_templates_code(user_templates, system_templates):
        user_template_code = (
            str(user_template.id) for user_template in user_templates
        )
        system_templat_code = (
            system_template.code for system_template in system_templates
        )
        return list(chain(user_template_code, system_templat_code))


class AllTemplatesView(DataTableView):

    def get(self, request, *args, **kwargs):
        param_args = json.loads(request.query_params["args"])
        self.check_param(param_args)
        param_args = self.params(request, param_args)
        query = self.get_query(request, *args, **kwargs)
        query = self.filters(
            query, param_args.get('filters', []), request
        )  # filter
        query = self.global_search(query, param_args)
        query = self.global_sort(query, param_args, request)

        filtered_total = len(query) if query else 0
        offset = param_args['offset'] \
            if param_args['offset'] < filtered_total else 0
        results = query[offset:offset + param_args['length']] \
            if query else []
        offset = offset + len(results)
        return Response(
            {
                'offset': offset,
                'total': filtered_total,
                'data': [self.trans_result(result) for result in results],
            }
        )

    @staticmethod
    def trans_result(result):
        del result["feature_code"]
        del result["index"]
        del result["lower_name"]
        return result

    @staticmethod
    def get_query(request, *args, **kwargs):
        username = request.user.username
        favorite_templates = [
            template['code']
            for template in FavoriteTemplate.objects.filter(
                username=username
            ).values('code')
        ]
        system_templates = []
        for template in Template.objects.filter(
                display=True
        ).iterator():
            system_template = template.as_dict(
                include=[
                    "code", "type", "name", "category",
                    "feature_code", "index"
                ]
            )
            system_template.update(
                username="",
                favorite=True if template.code in favorite_templates else False
            )
            system_templates.append(system_template)
        user_templates = []
        for template in UserTemplate.objects.filter(
                Q(type='public') | Q(username=username)
        ).iterator():
            user_template = template.as_dict(
                include=[
                    "type", "name", "category",
                    "feature_code", "username", "index"
                ]
            )
            code = str(template.id)
            user_template.update(
                code=code,
                favorite=True if code in favorite_templates else False
            )
            user_templates.append(user_template)
        template_frame = DataFrame(
            template for template in chain(system_templates, user_templates)
        )
        template_frame['lower_name'] = [x.lower() for x in template_frame.name]
        sorted_template_frame = template_frame.sort_values(
            by=['index', 'lower_name']
        ).reset_index(drop=True)
        query = sorted_template_frame.to_dict(orient='records')
        return query

    def filters(self, query, filters, request):
        username = request.user.username
        for field in filters:
            if field["prop"] == "feature_code":
                query = self.filter_feature_code(query, field['values'])
            if field["prop"] == "favorites":
                query = self.filter_favorite(query, field['values'])
            if field["prop"] == "type":
                query = self.filter_type(query, field['values'], username)
            if field['prop'] == 'category':
                query = self.filter_category(query, field['values'])
        return query

    @staticmethod
    def filter_feature_code(query, feature_codes):
        if feature_codes and feature_codes[0]:
            templates = []
            for template in query:
                template_code = template["feature_code"]
                if template_code:
                    if all((
                            re.search(code, feature_codes[0])
                            for code in template_code.strip().split(",")
                    )):
                        templates.append(template)
                else:
                    templates.append(template)
            return templates
        return query

    @staticmethod
    def filter_favorite(query, favorites):
        if favorites and isinstance(favorites[0], bool):
            return [
                template for template in query
                if template['favorite'] == favorites[0]
            ]
        return query

    @staticmethod
    def filter_type(query, types, username):
        if types:
            template_type = types[0]
            if template_type == "private":
                return [
                    template for template in query
                    if template['username'] == username
                ]
        return query

    @staticmethod
    def filter_category(query, categories):
        if categories:
            category = categories[0]
            if category and category != 'All':
                templates = []
                for template in query:
                    template_category = [
                        tmp.strip()
                        for tmp in template['category'].strip().split(",")
                    ]
                    if category in template_category:
                        templates.append(template)
                return templates
        return query

    @staticmethod
    def global_search(query, param_args):
        if 'search' not in param_args or not query:
            return query
        else:
            search = param_args['search']
            props = search['props']
            keyword = search['keyword']
            if not keyword:
                return query
            if "name" in props:
                query = [
                    template for template in query
                    if keyword.lower() in template['name'].lower()
                ]
            return query

    def global_sort(self, query, param_args, request):
        if 'sort' not in param_args or not query:
            return query
        else:
            username = request.user.username
            sort = param_args['sort']
            prop = sort['prop']
            order = sort['order']
            if prop == "alphabetical":
                return self.sort_by_alphabetical(query, order)
            elif prop == "mostly_used":
                return self.sort_by_mostly_used(
                    query, order, username
                )
            elif prop == "latest_used":
                return self.sort_by_latest_used(query, order, username)
            else:
                return query

    @staticmethod
    def sort_by_alphabetical(query, order):
        query.sort(
            key=lambda x: x['name'].lower(),
            reverse=True if order == "descend" else False
        )
        return query

    @staticmethod
    def sort_by_mostly_used(query, order, username):
        if order == "descend":
            return query
        mostly_used = [
            template['template_code']
            for template in TemplateJob.objects.filter(
                create_time__gte=timezone.now()-datetime.timedelta(days=30),
                username=username
            ).values('template_code').annotate(
                mostly_used=Count('template_code')
            ).order_by('-mostly_used').iterator()
        ]
        exist_mostly_used = []
        for template_code in mostly_used:
            for index, template in enumerate(query):
                if template_code == template["code"]:
                    exist_mostly_used.append(template)
                    del query[index]
                    break
        return list(chain(exist_mostly_used, query))

    @staticmethod
    def sort_by_latest_used(query, order, username):
        if order == "descend":
            return query
        latest_used = [
            template['template_code']
            for template in TemplateJob.objects.filter(
                create_time__gte=timezone.now()-datetime.timedelta(days=30),
                username=username
            ).values('template_code').annotate(
                latest_time=Max('create_time')
            ).order_by('-latest_time').iterator()
        ]
        exist_latest_used = []
        for template_code in latest_used:
            for index, template in enumerate(query):
                if template_code == template["code"]:
                    exist_latest_used.append(template)
                    del query[index]
                    break
        return list(chain(exist_latest_used, query))
