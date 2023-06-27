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

import json
import logging
import socket
from os import path

import falcon
from falcon.media.validators import jsonschema

logger = logging.getLogger(__name__)


class Configure(object):
    def __init__(self, filepath):
        self.filepath = filepath

    def on_get(self, req, resp):
        if not path.exists(self.filepath):
            config = {}
        else:
            with open(self.filepath) as f:
                config = json.load(f)

        resp.media = self._form_config(config)

    @jsonschema.validate(
        {
            'type': 'object',
            'properties': {
                'username': {
                    'type': 'string',
                },
                'password': {
                    'type': 'string',
                },
                'server_address': {
                    'type': 'string',
                },
                'server_port': {
                    'type': 'integer',
                    'minimum': 0
                },
                'sender_address': {
                    'type': 'string',
                },
                'enabled': {
                    'type': 'boolean',
                },
                'ssl': {
                    'type': 'string',
                    'enum': ['TLS', 'SSL', 'NULL']
                }
            },
            'required': [
                'username',
                'password',
                'server_address',
                'server_port',
                'sender_address',
                'enabled',
                'ssl'
            ]
        }

    )
    def on_post(self, req, resp):
        with open(self.filepath, 'w') as f:
            json.dump(
                self._form_config(req.media),
                f
            )

        resp.status = falcon.HTTP_OK

    @staticmethod
    def _form_config(data):
        ssl = data.get('ssl', 'NULL')
        default_port = 465 if ssl == 'SSL' else 25
        return {
            'enabled': data.get('enabled', False),
            'username': data.get('username', ''),
            'password': data.get('password', ''),
            'server_address': data.get('server_address', ''),
            'server_port': data.get('server_port', default_port),
            'sender_address': data.get('sender_address', ''),
            'ssl': ssl,
        }


class Message(object):
    def __init__(self, filepath, timeout):
        self.filepath = filepath
        self.timeout = timeout

    @jsonschema.validate({
        'type': 'object',
        'properties': {
            'target': {
                'type': 'array',
                'minItems': 1,
                'items': {
                    'type': 'string'
                }
            },
            'title': {
                'type': 'string',
            },
            'msg': {
                'type': 'string',
            }
        },
        'required': [
            'target', 'title', 'msg',
        ]
    })
    def on_post(self, req, resp):
        if path.exists(self.filepath):
            with open(self.filepath) as f:
                config = json.load(f)
        else:
            config = {}

        if config.get('enabled', False):
            try:
                self.send_mail(
                    sender=config.get('sender_address', ''),
                    address=req.media['target'],
                    subject=req.media['title'],
                    data=req.media['msg'],
                    host=config.get('server_address', ''),
                    port=config.get('server_port', ''),
                    ssl=config.get('ssl', 'NULL'),
                    username=config.get('username', ''),
                    password=config.get('password', ''),
                    timeout=self.timeout
                )
                resp.status = falcon.HTTP_OK
                resp.media = {}
            except socket.error as e:
                raise falcon.HTTPBadRequest(
                    code=13002,
                    description='Mail test failed.'
                ) from e
        else:
            resp.status = falcon.HTTP_NO_CONTENT
            # resp.media = {}

    def send_mail(
            self,
            sender, address, subject, data,
            host, port, ssl, username, password, timeout
    ):
        try:
            client = self._make_client(
                host, port, ssl, username, password, timeout
            )
            self._send_mail(
                client, sender, address, subject, data
            )
        except socket.error:
            logger.exception('Fail to send email')
            raise

    @staticmethod
    def _make_client(
            host, port, ssl, username, password, timeout
    ):
        from smtplib import SMTP, SMTP_SSL
        if ssl == 'SSL':
            client = SMTP_SSL(host, port, timeout=timeout)
        elif ssl == 'TLS':
            client = SMTP(host, port, timeout=timeout)
            client.starttls()
        else:
            client = SMTP(host, port, timeout=timeout)

        if username and password:
            client.login(username, password)

        return client

    @staticmethod
    def _send_mail(client, sender, address, subject, data):
        from email.header import Header
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        msg = MIMEMultipart('alternative')
        msg.add_header('Content-Type', 'text/html;charset=utf-8')
        msg.attach(MIMEText(data, 'html', 'utf-8'))

        msg['SUBJECT'] = Header(subject, 'utf-8')
        msg['FROM'] = sender
        msg['TO'] = ', '.join(address)

        client.sendmail(sender, address, msg.as_string())
        logger.info('send mail success from:%s to:%s', sender, address)
