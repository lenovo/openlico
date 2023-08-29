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

from django.db.models import F

from ..models import JobTags, Tag


def get_all_tags(username, tags_list):
    tags = []
    for tag_name in tags_list:
        tag = Tag.objects.filter(username=username, name=tag_name)
        if tag.exists():
            tags.append(tag.first())
        else:
            tag = Tag.objects.create(name=tag_name, username=username, count=0)
            tags.append(tag)
    return tags


def add_tags_to_one_job(job, tags_list):
    for tag in tags_list:
        if tag in job.tags.all():
            JobTags.objects.filter(job_id=job.id, tag_id=tag.id).first().save()
        else:
            job.tags.add(tag)
        tag.count = F('count') + 1
        tag.save()
