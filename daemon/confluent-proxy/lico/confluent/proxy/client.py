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
from abc import ABCMeta, abstractmethod
from http.client import BAD_REQUEST, INTERNAL_SERVER_ERROR

import pymysql
from requests import HTTPError, Session

logger = logging.getLogger(__name__)

__all__ = ['ConfluentClient', 'ClusterConfluentClient']


class BaseConfluentClient(metaclass=ABCMeta):

    @abstractmethod
    def create_async(self, head, body):
        pass

    @abstractmethod
    def create_ssh_session(self, name, head, body):
        pass

    @abstractmethod
    def create_kvm_console(self, name, head, body):
        pass


class ConfluentClient(BaseConfluentClient):
    def __init__(  # nosec B107
            self,
            host='localhost', port='4005',
            user='', password='',
            timeout=30
    ):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.user = user
        self.password = password
        self.session = Session()

    def get_confluent_session(self):
        url = f'http://{self.host}:{self.port}/sessions/current/info'
        res = self.session.get(
            url,
            auth=(self.user, self.password),
            headers={'accept': 'application/json'},
            timeout=self.timeout
        )
        try:
            res.raise_for_status()
            if 'confluentsessionid' in res.cookies:
                self.session.cookies['confluentsessionid'] = \
                    res.cookies['confluentsessionid']
        except HTTPError:
            logger.exception(
                'Error while getting confluentsessionid, url is %s',
                url
            )

    def create_ssh_session(self, name, head, body):
        url = f'http://{self.host}:{self.port}/nodes/{name}/shell/sessions/'

        res = self.session.post(
            url,
            headers=head,
            json=body,
            timeout=self.timeout
        )
        status_code = res.status_code
        if BAD_REQUEST <= status_code < INTERNAL_SERVER_ERROR:
            self.get_confluent_session()
            res = self.session.post(
                url,
                headers=head,
                json=body,
                timeout=self.timeout
            )
        return res

    def create_kvm_console(self, name, head, body):
        url = f'http://{self.host}:{self.port}/nodes/{name}/console/session'

        res = self.session.post(
            url,
            headers=head,
            json=body,
            timeout=self.timeout
        )
        status_code = res.status_code
        if BAD_REQUEST <= status_code < INTERNAL_SERVER_ERROR:
            self.get_confluent_session()
            res = self.session.post(
                url,
                headers=head,
                json=body,
                timeout=self.timeout
            )
        return res

    def create_async(self, head, body):
        url = f'http://{self.host}:{self.port}/sessions/current/async'

        res = self.session.post(
            url,
            headers=head,
            json=body,
            timeout=self.timeout
        )
        status_code = res.status_code
        if BAD_REQUEST <= status_code < INTERNAL_SERVER_ERROR:
            self.get_confluent_session()
            res = self.session.post(
                url,
                headers=head,
                json=body,
                timeout=self.timeout
            )
        return res


class ClusterConfluentClient:

    def __init__(  # nosec B107
            self,
            host='127.0.0.1', port='4005',
            user='', password='',
            timeout=30, members=[],
            db_host='127.0.0.1', db_port='3306',
            db_database='lico', db_user='',
            db_pass=''
    ):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.user = user
        self.password = password
        self.members = members + [host]
        self.session = dict.fromkeys(
            members + [host], Session()
        )
        self.database = Database(
            db_host=db_host, db_database=db_database,
            db_port=int(db_port), db_user=db_user,
            db_pass=db_pass
        )

    def get_confluent_session(self, ipaddr=None):
        url = f'http://{self.host}:{self.port}/sessions/current/info'
        session = self.session[self.host]
        if ipaddr:
            url = f'http://{ipaddr}:{self.port}/sessions/current/info'
            session = self.session.get(ipaddr, Session())
        res = session.get(
            url,
            auth=(self.user, self.password),
            headers={'accept': 'application/json'},
            timeout=self.timeout
        )
        try:
            res.raise_for_status()
            if 'confluentsessionid' in res.cookies:
                session.cookies['confluentsessionid'] = \
                    res.cookies['confluentsessionid']
            return res
        except HTTPError:
            logger.exception(
                'Error while getting confluentsessionid, url is %s',
                url
            )

    def create_ssh_session(self, name, head, body):
        async_id = head.get("CONFLUENTASYNCID")
        session_data = body.get("session") if body else None
        if session_data:
            data = session_data
            select_db = self.database.select_by_session
        if async_id:
            data = async_id
            select_db = self.database.select_by_asyncid

        asyncid, sessionid, ipaddr = select_db(data)
        session = self.session[ipaddr]
        session.cookies.update({"confluentsessionid": sessionid})
        url = f'http://{ipaddr}:{self.port}/nodes/{name}/shell/sessions/'
        res = session.post(
            url,
            headers=head,
            json=body,
            timeout=self.timeout
        )
        if data == async_id:
            self.database.add_session(
                async_id=async_id,
                session_id=sessionid,
                ipaddr=ipaddr,
                session=res.json()["session"]
            )
        return res

    def create_kvm_console(self, name, head, body):
        async_id = head.get("CONFLUENTASYNCID")
        session_data = body.get("session") if body else None
        if session_data:
            data = session_data
            select_db = self.database.select_by_session
        if async_id:
            data = async_id
            select_db = self.database.select_by_asyncid
        asyncid, sessionid, ipaddr = select_db(data)
        session = self.session[ipaddr]
        session.cookies.update({"confluentsessionid": sessionid})
        url = f'http://{ipaddr}:{self.port}' \
              f'/nodes/{name}/console/session/'
        res = session.post(
            url,
            headers=head,
            json=body,
            timeout=self.timeout
        )
        if data == async_id:
            self.database.add_session(
                async_id=async_id,
                session_id=sessionid,
                ipaddr=ipaddr,
                session=res.json()["session"]
            )
        return res

    def create_async(self, head, body):
        async_id = body.get("asyncid") if body else None
        if async_id:
            asyncid, sessionid, ipaddr = self.database.select_by_asyncid(
                async_id=async_id
            )
            url = f'http://{ipaddr}:{self.port}/sessions/current/async'
            session = self.session[ipaddr]
            session.cookies.update({"confluentsessionid": sessionid})
            res = session.post(
                url,
                headers=head,
                json=body,
                timeout=self.timeout
            )
            return res
        else:
            from random import choice  # nosec B311
            ipaddr = choice(self.members) if self.members else self.host
            url = f'http://{ipaddr}:{self.port}/sessions/current/async'
            session = self.session[ipaddr]
            result = self.get_confluent_session(ipaddr=ipaddr)
            res = session.post(
                url,
                headers=head,
                json=body,
                timeout=self.timeout
            )
            sessionid = result.json()["sessionid"]
            self.database.insert_db(
                res.json()["asyncid"],
                sessionid,
                ipaddr
            )
            return res


class Database:

    def __init__(  # nosec B107
            self, db_host='127.0.0.1', db_database='lico',
            db_port=3306, db_user='', db_pass=''
    ):
        self.db_host = db_host
        self.db_database = db_database
        self.db_port = db_port
        self.db_user = db_user
        self.db_pass = db_pass

    def db_operation(self, sql, *args, commit=False):
        conn = pymysql.connect(
            host=self.db_host, user=self.db_user, password=self.db_pass,
            database=self.db_database, port=int(self.db_port)
        )
        with conn.cursor() as cursor:
            cursor.execute(sql, args)
            if commit:
                conn.commit()
            else:
                result = cursor.fetchone()
                return result
        conn.close()

    def insert_db(self, async_id, session_id, ipaddr):
        insert_sql = "INSERT INTO cluster_asyncid" \
                     "(asyncid, sessionid, ipaddr, create_time) " \
                     "VALUES (%s, %s, %s, NOW())"
        self.db_operation(insert_sql, async_id,
                          session_id, ipaddr, commit=True)

    def select_by_asyncid(self, async_id):
        select_sql = "SELECT asyncid, sessionid, ipaddr " \
                     "FROM cluster_asyncid WHERE asyncid=%s"
        result = self.db_operation(select_sql, async_id)
        if result:
            return result
        logger.info("no data for async_id: ", async_id, exc_info=True)
        return None, None, None

    def select_by_session(self, session):
        select_sql = "SELECT asyncid, sessionid, ipaddr " \
                     "FROM cluster_asyncid WHERE session=%s"
        result = self.db_operation(select_sql, session)
        if result:
            return result
        logger.info("no data for session_data", session, exc_info=True)
        return None, None, None

    def add_session(self, async_id, session_id, ipaddr, session):
        add_session_sql = "INSERT INTO cluster_asyncid(asyncid, " \
                          "sessionid, ipaddr, session, create_time" \
                          ") VALUES (%s, %s, %s, %s, NOW())"
        self.db_operation(add_session_sql, async_id, session_id,
                          ipaddr, session, commit=True)
