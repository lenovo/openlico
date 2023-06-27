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


def cleanNodesSensitiveContent(configure_file):
    from os import path
    if path.exists(configure_file):
        with open(configure_file, 'rb') as f:
            import io

            import chardet
            content = f.read()
            encoding = chardet.detect(content)['encoding']
            f = io.StringIO(content.decode(
                encoding if encoding == 'utf-8' else 'gbk'
            ))
            lines = f.readlines()
            f.seek(0)
            f.truncate()
            ipmi_user_idx = 0
            ipmi_pwd_idx = 0
            for line in lines:
                if ipmi_user_idx > 0 and ipmi_pwd_idx > 0 \
                        and line.find(',') >= 0:
                    cells = line.split(',')
                    if len(cells[ipmi_user_idx]) > 0:
                        cells[ipmi_user_idx] = '******'
                    if len(cells[ipmi_pwd_idx]) > 0:
                        cells[ipmi_pwd_idx] = '******'
                    f.write(','.join(cells))
                else:
                    f.write(line)
                    # locate the nodes section
                    if line.startswith('node') and line.find(',') >= 0:
                        columns = line.split(',')
                        for idx in range(len(columns)):
                            if columns[idx] == 'ipmi_user':
                                ipmi_user_idx = idx
                            if columns[idx] == 'ipmi_pwd':
                                ipmi_pwd_idx = idx
            with open(configure_file, 'w') as cf:
                cf.write(f.getvalue())
