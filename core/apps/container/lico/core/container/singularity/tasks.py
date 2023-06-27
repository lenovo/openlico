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

import pwd
import stat
from os import path

from py.path import local

from lico.core.base.celery import app

from .models import SingularityImage
from .utils import TaskStatus, change_owner, user_image_path


@app.task(time_limit=600, ignore_result=True)
def copy_image(image_id, origin_path):
    image = SingularityImage.objects.get(id=image_id)
    image.status = TaskStatus.STARTED.value
    image.save()
    username = image.username
    if username != '':
        user = pwd.getpwnam(username)
        user_path = user_image_path(user.pw_dir)
        user_path.chown(user.pw_uid, user.pw_gid)

    target_path = local(image.image_path)
    try:
        local(origin_path).copy(target_path)
        change_owner(image, target_path)
        image.status = TaskStatus.SUCCESS.value
        image.save()
    except Exception:
        image.status = TaskStatus.FAILURE.value
        image.save()
        if target_path.exists():
            target_path.remove()
        raise


@app.task(time_limit=600, ignore_result=True)
def download_image(origin_path, target_path, uid, gid):
    target_path = local(target_path)
    target_basename = path.basename(target_path)
    target_dirname = path.dirname(target_path)
    hide_target_path = local(target_dirname).join(f".{target_basename}")
    try:
        local(origin_path).copy(hide_target_path)
        hide_target_path.chown(uid, gid)
        hide_target_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
        hide_target_path.move(target_path)
    except Exception:
        if hide_target_path.exists():
            hide_target_path.remove()
        if target_path.exists():
            target_path.remove()
        raise
