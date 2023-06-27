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

import pymysql


class AuthDatabase:

    def __init__(self,
                 db_host='127.0.0.1',
                 db_database='lico',
                 db_port=3306
                 ):

        from lico.password import fetch_pass
        db_user, db_pass = fetch_pass('mariadb')

        self.conn = pymysql.connect(host=db_host,
                                    user=db_user,
                                    password=db_pass,
                                    database=db_database,
                                    port=int(db_port))
        self.cursor = self.conn.cursor()
        # get latest key
        self.query_key_sql = "SELECT `key` FROM base_secretkey " \
                             "ORDER BY id DESC LIMIT 1"
        self.query_args = {}

    def get_key(self):
        key = None
        try:
            self.conn.ping(reconnect=True)
            self.cursor.execute(self.query_key_sql, self.query_args)
            results = self.cursor.fetchall()
            for row in results:
                key = row[0]
        except Exception as e:
            raise e

        return key

    def close(self):
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
