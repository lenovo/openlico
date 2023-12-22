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

from django.conf import settings
from rest_framework.response import Response
from rest_framework.views import APIView


class ConfigView(APIView):
    def get(self, request):
        return Response(
            {
                key.lower(): value
                for key, value in settings.LICO.items()
            }
        )


class VersionView(APIView):
    def get(self, request):
        from ._version import build_date, version
        from .subapp import iter_sub_apps

        return Response(
            {
                'version': version,
                'build_date': build_date,
                'subapps': [
                    {
                        'name': app.dist.project_name,
                        'version': app.dist.version
                    }
                    for app in iter_sub_apps()
                ]
            }
        )


class ApplicationConfigView(APIView):
    app = None

    def get(self, request):
        return Response(
            self.app.on_show_config(settings)
            if self.app is not None else {}
        )
