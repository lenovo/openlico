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
import os
import shutil
from datetime import datetime
from enum import Enum

from apscheduler.events import (
    EVENT_JOB_ADDED, EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, EVENT_JOB_SUBMITTED,
    JobExecutionEvent,
)
from apscheduler.schedulers.base import BaseScheduler
from py.path import local

from lico.ssh import RemoteSSH

from .exception import (
    INITERROR, OUTPUTERROR, RUNERROR, HTTPBadRequest, MaxJobsReached,
)

logger = logging.getLogger(__name__)


class BuildJobStatus(Enum):
    PENDING = 'PENDING'
    SUBMITTED = 'SUBMITTED'
    EXECUTED = 'EXECUTED'
    ERROR = 'ERROR'


class BuildJobManager:
    def __init__(
            self, scheduler: BaseScheduler, max_jobs: int, builder: str,
            port: int = 22, username: str = None, password: str = None
    ):
        self.builder = builder
        self.scheduler = scheduler
        self.records = {}
        self.infos = {}
        self.errors = {}
        self.max_jobs = max_jobs
        self.port = port
        self.username = username
        self.password = password
        scheduler.add_listener(
            self._listener,
            EVENT_JOB_ADDED | EVENT_JOB_SUBMITTED |
            EVENT_JOB_EXECUTED | EVENT_JOB_ERROR
        )

    def add_job(self, *args, **kwargs):
        if self.running_jobs >= self.max_jobs:
            raise MaxJobsReached
        else:
            job = self.scheduler.add_job(
                self.task, args=args, kwargs=kwargs,
                next_run_time=datetime.utcnow()
            )
            self.infos[job.id] = kwargs["workspace"]

            return job

    def cancel_job(self, job_id):

        if job_id not in self.infos:
            logger.warning('Job not exists: %s', job_id)
            return

        workspace = self.infos[job_id]
        self._cancel_job(workspace).ensure()

    @staticmethod
    def _kill_process(pid):
        import psutil
        try:
            process = psutil.Process(pid)
            for child in process.children(recursive=True):
                child.kill()
            process.kill()
        except psutil.NoSuchProcess:
            logger.warning(
                'No Such Process %s',
                process.pid, exc_info=True
            )

    def _listener(self, event: JobExecutionEvent):
        job_id = event.job_id
        code = event.code
        if code == EVENT_JOB_ADDED:
            self.records[job_id] = BuildJobStatus.PENDING
        elif code == EVENT_JOB_SUBMITTED:
            self.records[job_id] = BuildJobStatus.SUBMITTED
        elif code == EVENT_JOB_EXECUTED:
            self.records[job_id] = BuildJobStatus.EXECUTED
            if job_id in self.infos:
                tmp_workspace = self.infos[job_id]
                if os.path.exists(tmp_workspace):
                    shutil.rmtree(tmp_workspace, ignore_errors=True)
                del self.infos[job_id]
        elif code == EVENT_JOB_ERROR:
            self.records[job_id] = BuildJobStatus.ERROR
            if isinstance(event.exception, HTTPBadRequest):
                self.errors[job_id] = event.exception.description
            if job_id in self.infos:
                tmp_workspace = self.infos[job_id]
                if os.path.exists(tmp_workspace):
                    shutil.rmtree(tmp_workspace, ignore_errors=True)
                del self.infos[job_id]

    def _running_jobs(self):
        for job_id, status in self.records.items():
            if status in (
                BuildJobStatus.PENDING, BuildJobStatus.SUBMITTED
            ):
                yield job_id

    @property
    def running_jobs(self):
        return sum(1 for _ in self._running_jobs())

    def _cancel_job(self, workspace: str):
        return local(workspace).join(f'.cancel.{self.builder}.job')

    def ensure_cancel(self, workspace):
        return self._cancel_job(workspace).exists()

    def task(  # noqa: C901
            self, fs, workspace, output, data,
            user, log_path, *args, **kwargs
    ):
        import threading
        import time
        from multiprocessing import Process

        # async upload
        timer = None

        def async_upload(upload_list):
            nonlocal timer
            for path in upload_list:
                if os.path.exists(path['src']):
                    try:
                        fs.upload_file(path['src'], path['dst'])
                    except Exception:
                        logger.error(f"Failed to upload file "
                                     f"from {path['src']} to {path['dst']}")
                        continue
            timer = threading.Timer(2, async_upload, (upload_list,))
            timer.start()

        upload_list = []
        for path in output:
            if path.get("auto-sync"):
                upload_list.append(path)

        if upload_list:
            async_upload(upload_list)

        # main
        try:
            # init
            local(log_path).write(
                b"Start to prepare the work environment\n", "ab"
            )

            def download_dir():

                for item in data:
                    if not fs.filesystem.path_exists(item['src']) or \
                            not fs.filesystem.path_isdir(item['src']):
                        raise INITERROR
                    fs.filesystem.download_directory(item['src'], item['dst'])

            init_process = Process(target=download_dir)
            init_process.start()
            while init_process.is_alive():
                time.sleep(1)
                if self.ensure_cancel(workspace):
                    self._kill_process(init_process.pid)
                    return

            if init_process.exitcode:
                raise INITERROR
            local(log_path).write(
                b"Finished to work environment preparation\n", "ab"
            )
            # run
            log_stream = local(log_path).open('a')

            def run():
                from tempfile import TemporaryFile
                with TemporaryFile("w+") as tf:
                    tf.write(kwargs.get('input', b'').decode())
                    tf.seek(0)
                    with RemoteSSH(
                            host=self.builder, port=self.port,
                            username=self.username, password=self.password
                    ) as conn:
                        with conn.cd(workspace):
                            res = conn.run(
                                [kwargs.get("args")], in_stream=tf,
                                out_stream=log_stream, err_stream=log_stream
                            )
                            return res.return_code

            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(run)
                while future.running():
                    time.sleep(1)
                    if self.ensure_cancel(workspace):
                        future.cancel()
                        return
                result = future.result()
                if result:
                    logger.error(
                        f"The script return code is {result}"
                    )
                    raise RUNERROR
        except Exception:
            raise
        else:
            for path in output:
                if path.get('src') and os.path.exists(path['src']):
                    try:
                        fs.upload_file(path['src'], path['dst'])
                    except Exception:
                        logger.error(f"Failed to upload file "
                                     f"from {path['src']} to {path['dst']}")
                        raise OUTPUTERROR
        finally:
            for path in output:
                if path.get('src') and path.get('auto-sync'):
                    try:
                        fs.upload_file(path['src'], path['dst'])
                    except Exception:
                        logger.error(f"Failed to upload file "
                                     f"from {path['src']} to {path['dst']}")
                        continue

                if fs.filesystem.path_exists(path['dst']):
                    fs.filesystem.chown(path['dst'], user.pw_uid, user.pw_gid)

            if timer is not None:
                timer.cancel()

            if os.path.exists(workspace):
                shutil.rmtree(workspace, ignore_errors=True)
