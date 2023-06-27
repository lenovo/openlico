# -*- coding:utf-8 -*-
# Copyright 2020-present Lenovo
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

import datetime
import logging
import uuid
from abc import ABCMeta, abstractmethod
from io import BytesIO

from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.translation import ugettext as _
from weasyprint import HTML
from xlsxwriter.workbook import Workbook

logger = logging.getLogger(__name__)


def _counter(start=0, step=1):
    count = start
    while True:
        val = yield count
        count += step if val is None else val


class ReportBase(metaclass=ABCMeta):

    def __init__(
            self, operator, headline, data, title, doctype,
            start_time, end_time, creator, create_time, template,
            subtitle, page_direction, fixed_offset, time_range_flag
    ):
        self.operator = operator
        self.headline = self.translate(headline)
        self.data = data
        self.title = _(title)
        self.doctype = doctype
        self.fixed_offset = fixed_offset
        self.export_time = datetime.datetime.now(
            tz=self.fixed_offset).strftime("%F %T")
        self.report_export = getattr(self, 'export_' + doctype)
        self.export_filename = str(uuid.uuid1())
        self.start_time = start_time
        self.end_time = end_time
        self.creator = creator
        self.create_time = create_time
        self.template = template
        self.subtitle = _(subtitle)
        self.page_direction = page_direction
        self.time_range_flag = time_range_flag

        if self.time_range_flag:
            self.create_info = ' '.join([
                self.creator,
                _(u'created at'),
                self.create_time.strftime('%F %T')
            ])
        else:
            self.create_info = self.creator + ' ' + _(u'created at') + ' ' + \
                self.create_time.strftime('%F %T') + '\n' + \
                _(u'data cycle') + ':' + self.start_time.strftime('%F %T') + \
                ' - ' + self.end_time.strftime('%F %T')

    '''
    :param type is list[str] or str such as ["a",["b"]] or "b"
    :function  translate
    '''

    def translate(self, param):
        if isinstance(param, str):
            return _(param)
        if isinstance(param, list):
            ret = []
            for item in param:
                if isinstance(item, str):
                    ret.append(_(item))
                elif isinstance(item, list):
                    ret.append(self.translate(item))
            else:
                return ret
        return None

    @abstractmethod
    def export_html(self):
        pass

    @abstractmethod
    def export_pdf(self):
        pass

    @abstractmethod
    def export_xlsx(self):
        pass


class ReportExporter(ReportBase):

    def _generate_html(self):
        return render_to_string(
            self.template,
            context={
                'operator': self.operator,
                'title': self.title,
                'subtitle': self.subtitle,
                'headline': self.headline,
                'data': enumerate(self.data, 1),
                'start_time': self.start_time.strftime('%F %T'),
                'end_time': self.end_time.strftime('%F %T'),
                'creator': self.creator,
                'create_time': self.create_time.strftime('%F %T'),
                'page_direction': self.page_direction
            }
        )

    def export_html(self):
        html = self._generate_html()
        return BytesIO(html.encode()), '.html'

    def export_pdf(self):
        stream = BytesIO()
        html = HTML(string=self._generate_html())
        html.write_pdf(stream)
        stream.seek(0)
        return stream, '.pdf'

    def export_xlsx(self):
        stream = BytesIO()
        with Workbook(stream, dict(in_memory=True)) as book:
            sheet = book.add_worksheet(self.title)
            counter = _counter()
            # write title
            title_merge_format = book.add_format({
                'align': 'center',
                'bold': True,
                'valign': 'vcenter',
                'font_size': 25,
                'font_name': 'Arial'
            })

            sheet.merge_range(
                next(counter), counter.send(0), 0, len(self.headline) - 1,
                self.title,
                title_merge_format
            )

            # write info
            info_merge_format = book.add_format({
                'align': 'right',
                'bold': True,
                'text_wrap': 'text_wrap',
                'valign': 'vcenter',
                'font_size': 10,
                'font_name': 'Arial'
            })
            sheet.merge_range(
                next(counter), 0, counter.send(1), len(self.headline) - 1,
                self.create_info,
                info_merge_format
            )
            # write table head
            head_merge_format = book.add_format({
                'align': 'center',
                'bold': True,
                'valign': 'vcenter',
                'font_name': 'Arial',
                'text_wrap': 'text_wrap',
                'font_size': 10
            })
            next(counter)
            for colx, value in enumerate(self.headline):
                sheet.write(
                    counter.send(0), colx, value, head_merge_format
                )
            # set frozen
            sheet.freeze_panes(4, 0)
            # write table data
            for row in self.data:
                next(counter)
                for colx, value in enumerate(row):
                    if (
                            isinstance(value, datetime.datetime) or
                            isinstance(value, datetime.date) or
                            isinstance(value, datetime.time)
                    ):
                        value = (timezone.localtime(value)).strftime("%F %T")
                    sheet.write(counter.send(0), colx, value)

        stream.seek(0)
        return stream, '.xlsx'
