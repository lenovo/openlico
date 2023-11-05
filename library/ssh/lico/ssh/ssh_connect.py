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

from collections import defaultdict
from subprocess import list2cmdline  # nosec B404

import paramiko
from fabric import Connection
from invoke.exceptions import Failure
from paramiko.ssh_exception import SSHException


class RemoteSSH:
    def __init__(self, host='127.0.0.1', port=22, username=None,
                 password=None, connect_timeout=60, private_key_file=None):
        """
        initialize
        :param host: hostname or ip address
        :param port: port number
        :param username: username
        :param password: password
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.private_key_file = private_key_file
        self.connect_timeout = connect_timeout
        self.connect_kwargs = self._format_connect_kwargs()
        self.connection = Connection(
            self.host,
            port=self.port,
            user=self.username,
            connect_timeout=self.connect_timeout,
            connect_kwargs=self.connect_kwargs
        )

    def _format_connect_kwargs(self):
        connect_kwargs = defaultdict()
        if self.private_key_file:
            pkey = paramiko.RSAKey.from_private_key_file(
                self.private_key_file)
            connect_kwargs['pkey'] = pkey
        if self.password:
            connect_kwargs['password'] = self.password
        return connect_kwargs

    def close(self):
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def cd(self, path: str):
        """
        Use as the context manager,like:
            with conn.cd(path):
                conn.run()
        :param path:
        """
        return self.connection.cd(path=path)

    def sftp(self):
        return self.connection.sftp()

    def is_connected(self):
        return self.connection.is_connected

    def async_run(self, cmd: list, env: dict = None,
                  in_stream=None, out_stream=None,
                  err_stream=None, command_timeout=None, **kwargs):
        """
        If you want to use the parameter 'asynchronous=True' to execute the
        asynchronous tasks,please ensure that the connection is alive when
        the tasks are being submitted.
        The type of result is invoke.runners.Promise.You can use join()
        to get the output but it will block the processes util the
        subprocess is exited.
        params:
        :param cmd: The shell command to execute.
        :param out_stream: A file-like stream object to
                           which the subprocess’ standard output should
                           be written. If None (the default),
                           sys.stdout will be used.
        :param err_stream: A file-like stream object.
        :param in_stream:  A file-like stream object.
        :param command_timeout: If the commands take longer than it,
                                it will raise CommandTimedOut.
        :param env: Supply a dict here to update that child environment.
        """
        try:
            result = self.connection.run(
                list2cmdline(cmd),
                in_stream=in_stream,
                out_stream=out_stream,
                err_stream=err_stream,
                asynchronous=True,
                timeout=command_timeout,
                env=env,
                **kwargs
            )
            return result
        except Failure as e:
            raise Exception(e.result)
        except SSHException as e:
            raise Exception(
                "Exception raised by failures "
                "in SSH2 protocol negotiation or logic errors."
            ) from e
        except Exception:
            raise

    def run(self, cmd: list, env: dict = None, in_stream=None,
            out_stream=None, err_stream=None, hide=True,
            command_timeout=None, **kwargs):
        """
        params:
        :param cmd: The shell command to execute.
        :param out_stream: A file-like stream object to
                           which the subprocess’ standard output should
                           be written. If None (the default),
                           sys.stdout will be used.
        :param err_stream: A file-like stream object.
        :param in_stream:  A file-like stream object.
        :param hide: Copy the out to the controlling terminal.
        :param command_timeout: If the commands take longer than it,
                                it will raise CommandTimedOut.
        :param env: Supply a dict here to update that child environment.
        """
        try:
            result = self.connection.run(
                list2cmdline(cmd),
                in_stream=in_stream,
                out_stream=out_stream,
                err_stream=err_stream,
                hide=hide,
                asynchronous=False,
                timeout=command_timeout,
                env=env,
                **kwargs
            )
            return result
        except Failure as e:
            raise Exception(e.result)
        except SSHException as e:
            raise Exception(
                "Exception raised by failures "
                "in SSH2 protocol negotiation or logic errors."
            ) from e
        except Exception:
            raise

    def set_env(self, env_dict: dict):
        env = self.connection.config.run.get("env", {})
        for k, v in env_dict.items():
            env[k] = v
        self.connection.config.run['env'] = env
        self.connection.config.inline_ssh_env = True
