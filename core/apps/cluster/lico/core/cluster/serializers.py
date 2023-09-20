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

from rest_framework import serializers

from . import models


class NodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Node
        fields = "__all__"


# XXX
# below serializers use models which inherit from contrib.Model
# its Manager introduces a bug for rest framework when serializing
# nested relationships (TypError: related manager is not iterable)
# we workaround that by using serializer method fields
class RackSerializer(serializers.ModelSerializer):
    nodes = serializers.SerializerMethodField()

    class Meta:
        model = models.Rack
        fields = (
            "id",
            "name",
            "col",
            "row",
            "nodes",
        )

    def get_nodes(self, obj):
        return NodeSerializer(obj.nodes.all(), many=True).data


class RowSerializer(serializers.ModelSerializer):
    racks = serializers.SerializerMethodField()

    class Meta:
        model = models.Row
        fields = (
            "id",
            "name",
            "racks",
        )

    def get_racks(self, obj):
        return RackSerializer(obj.racks.all(), many=True).data


class RoomSerializer(serializers.ModelSerializer):
    rows = serializers.SerializerMethodField()

    class Meta:
        model = models.Room
        fields = (
            "id",
            "name",
            "location",
            "rows",
        )

    def get_rows(self, obj):
        return RowSerializer(obj.rows.all(), many=True).data
