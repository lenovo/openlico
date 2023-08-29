# -*- coding:utf-8 -*-
# Copyright 2018-present Lenovo
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

import csv
import datetime
import logging
import uuid
from abc import ABCMeta, abstractmethod
from io import BytesIO, StringIO

from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.translation import ugettext as _
from six import add_metaclass
from weasyprint import HTML
from xlsxwriter.workbook import Workbook

logger = logging.getLogger(__name__)


def _counter(start=0, step=1):
    count = start
    while True:
        val = yield count
        count += step if val is None else val


datetime_format_str = "%F %T"


@add_metaclass(ABCMeta)
class ReportBase(object):
    def __init__(self, operator, headline, data, title, doctype,
                 start_time, end_time, creator, create_time, template,
                 subtitle, page_direction, fixed_offset):
        datetime_now = datetime.datetime.now(tz=fixed_offset)
        self.operator = operator
        self.headline = self.translate(headline)
        self.data = data
        self.title = _(title)
        self.doctype = doctype
        self.fixed_offset = fixed_offset
        self.export_time = datetime_now.strftime(datetime_format_str)
        self.report_export = getattr(self, 'export_' + doctype)
        self.export_filename = str(uuid.uuid1())
        self.start_time = start_time
        self.end_time = end_time
        self.creator = creator
        self.create_time = create_time
        self.template = template
        self.subtitle = _(subtitle)
        self.page_direction = page_direction
        self.create_info = ' '.join([
            self.creator,
            _('monitor.created at'),
            self.create_time.strftime(datetime_format_str)
        ])

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


class GroupReportExporter(ReportBase):

    def _generate_html(self):
        if self.template == 'report/node_running_statistics.html' and \
                self.doctype == 'pdf':
            self.template = 'report/node_running_statistics_pdf.html'
        return render_to_string(
            self.template,
            context={
                'title': self.title,
                'operator': self.operator,
                'subtitle': self.subtitle,
                'headline': self.headline,
                'data': (
                    (group_title_data, enumerate(group_data, 1))
                    for (group_title_data, group_data) in self.data
                ),
                'start_time': self.start_time.strftime(datetime_format_str),
                'end_time': self.end_time.strftime(datetime_format_str),
                'creator': self.creator,
                'create_time': self.create_time.strftime(datetime_format_str),
                'page_direction': self.page_direction
            }
        )

    def export_html(self):
        filename = self.export_filename + '.html'
        html = self._generate_html()
        return BytesIO(html.encode()), filename

    def export_pdf(self):
        filename = self.export_filename + '.pdf'
        stream = BytesIO()
        html = HTML(string=self._generate_html())
        html.write_pdf(stream)
        stream.seek(0)
        return stream, filename

    def export_xlsx(self):
        stream = BytesIO()
        group_title, group_headline = self.headline
        filename = self.export_filename + '.xlsx'
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
                next(counter), counter.send(0), 0,
                len(group_headline) - 1,
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
                next(counter), 0, counter.send(1), len(group_headline) - 1,
                self.create_info,
                info_merge_format
            )

            # write group
            head_merge_format = book.add_format({
                'align': 'center',
                'bold': True,
                'valign': 'vcenter',
                'font_name': 'Arial',
                'text_wrap': 'text_wrap',
                'font_size': 10
            })
            for group_title_data, group_data in self.data:
                # write group head
                sheet.merge_range(
                    next(counter), 0, counter.send(0), len(group_headline) - 1,
                    '{}: {}'.format(group_title, group_title_data),
                    head_merge_format
                )
                next(counter)
                for colx, value in enumerate(group_headline):
                    sheet.write(
                        counter.send(0), colx, value,
                        head_merge_format
                    )
                # write group data
                for row in group_data:
                    next(counter)
                    for colx, value in enumerate(row):
                        if (
                                isinstance(value, datetime.datetime) or
                                isinstance(value, datetime.date) or
                                isinstance(value, datetime.time)
                        ):
                            value = (timezone.localtime(value)) \
                                .strftime(datetime_format_str)
                        sheet.write(counter.send(0), colx, value)
                # split one line
                next(counter)

        stream.seek(0)
        return stream, filename

    def export_csv(self):
        data = []
        for hostname, value in self.data:
            for v in value:
                timestamp, metric = v
                ts = datetime.datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
                data.append((ts, metric, hostname))

        data.sort(key=lambda item: item[0])

        stream = StringIO()
        writer = csv.writer(stream)
        writer.writerow(('Timestamp', 'Metric', 'Hostname'))
        for item in data:
            writer.writerow(item)

        stream.seek(0)

        return stream, f"{self.export_filename}.csv"
