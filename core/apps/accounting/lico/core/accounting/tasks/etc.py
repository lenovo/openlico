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

from string import ascii_uppercase

from ..models import Gresource

DEFAULT_GRES_START_COL = 10
DEFAULT_HEAD_BEGIN_LINE = 8
CLUSTER_CRES_START_COL = 9

GRES = list()

for gres in Gresource.objects.filter(billing=True).order_by('id'):
    GRES.append(
        gres.as_dict(
            include=['code', 'display_name', 'unit']
        )
    )


GRES_HEAD_DICT = dict()
GRES_HEAD_DICT2 = dict()
for gres in GRES:
    GRES_HEAD_DICT[gres['code']] = [
        "Django.accounting.bill.Hour",
        "Django.accounting.bill.Used",
        "Django.accounting.bill.Cost"
    ]

    GRES_HEAD_DICT2[gres['code']] = [
        "Django.accounting.bill.Hour",
        "Django.accounting.bill.Cost"
    ]


def write_pure(color):
    return {'fill_color': color}


def write_right(color):
    return {'fill_color': color, 'hori': 'right'}


def write_right_data(color):
    return {'fill_color': color, 'hori': 'right', 'data_format': True}


def write_right_decimal(color):
    return {'fill_color': color, 'hori': 'right', 'keep_decimal': True}


def write_right_currency(color):
    return {'fill_color': color, 'hori': 'right', 'curr_style': True}


def _sub_cell(gres_head, gres_col, gres_row):
    return [
                {
                    "title": gres,
                    "start_cell":
                        "{0}{1}".format(
                            ascii_uppercase[gres_col+inx], gres_row
                        ),
                    "end_cell":
                        "{0}{1}".format(
                            ascii_uppercase[gres_col+inx], gres_row
                        )}
                for inx, gres in enumerate(gres_head)
            ]


def gres_head_dict(gres_col, gres_row, user_daily_type=False):
    head_list = list()
    index = 0
    for gres in GRES:
        head_dict = dict()
        head_dict["title"] = gres['display_name']
        if user_daily_type:
            head_dict["start_cell"] = \
                "{0}{1}".format(
                    ascii_uppercase[gres_col+index], gres_row)
            head_dict["end_cell"] = \
                "{0}{1}".format(
                    ascii_uppercase[gres_col+index+2], gres_row)
            head_dict["sub_cell"] = _sub_cell(
                GRES_HEAD_DICT[gres['code']], gres_col+index, gres_row+1)
            index += 3
        else:
            head_dict["start_cell"] = \
                "{0}{1}".format(ascii_uppercase[gres_col+index], gres_row)
            head_dict["end_cell"] = \
                "{0}{1}".format(ascii_uppercase[gres_col+index+1], gres_row)
            head_dict["sub_cell"] = _sub_cell(
                GRES_HEAD_DICT2[gres['code']], gres_col+index, gres_row+1)
            index += 2
        head_list.append(head_dict)
    return head_list


def gres_data_style(begin_col):
    gres_style_list = list()
    for col in range(0, len(GRES)*2, 2):
        gres_style_list.extend(
            [
                {'%s{row}' % (
                    ascii_uppercase[begin_col+col]): write_right_decimal
                 },
                {'%s{row}' % (
                 ascii_uppercase[begin_col+col+1]): write_right_currency}
            ]
        )
    return gres_style_list


def gres_end_line_style(begin_col):
    gres_end_line_list = list()
    for col in range(0, len(GRES) * 2, 2):
        gres_end_line_list.extend([
            {'start_cell': '%s{row}' % (ascii_uppercase[begin_col+col]),
             'end_cell': '%s{row}' % (ascii_uppercase[begin_col+col]),
             'value': '=SUM(%s{start_row}:%s{end_row})' % (
                 ascii_uppercase[begin_col+col], ascii_uppercase[begin_col+col]
             )},
            {'start_cell': '%s{row}' % (ascii_uppercase[begin_col+1+col]),
             'end_cell': '%s{row}' % (ascii_uppercase[begin_col+1+col]),
             'value': '=SUM(%s{start_row}:%s{end_row})' % (
                 ascii_uppercase[begin_col+1+col],
                 ascii_uppercase[begin_col+1+col])}
        ])
    return gres_end_line_list


def get_create_info(bill_name, **kwargs):
    return {
        'User_Daily_Bills': {
            'title': {
                'A2': 'Bill.User',
                'A3': 'Bill.Billing_Group',
                'A4': 'Bill.Billing_Date',
                'A5': 'Bill.Create_Time',
                'A6': 'Bill.Total_Cost'
            },
            'value': {
                'B2': kwargs.get('user', ''),
                'B3': kwargs.get('bill_group', ''),
                'B4': kwargs.get('bill_date', ''),
                'B5': kwargs.get('create_time', ''),
                'B6': kwargs.get('total', ''),
            },
            'currency_cell': 'B6'
        },
        'User_Monthly_Bills': {
            'title': {
                'A2': 'Bill.User',
                'A3': 'Bill.Start_Time',
                'A4': 'Bill.End_Time',
                'A5': 'Bill.Create_Time',
                'A6': 'Bill.Total_Cost'
            },
            'value': {
                'B2': kwargs.get('user', ''),
                'B3': kwargs.get('start_time', ''),
                'B4': kwargs.get('end_time', ''),
                'B5': kwargs.get('create_time', ''),
                'B6': kwargs.get('total', ''),
            },
            'currency_cell': 'B6'
        },
        'Daily_Summary_Bills': {
            'title': {
                'A2': 'Bill.Billing_Date',
                'A3': 'Bill.Create_Time',
                'A4': 'Bill.Total_Cost'
            },
            'value': {
                'B2': kwargs.get('bill_date', ''),
                'B3': kwargs.get('create_time', ''),
                'B4': kwargs.get('total', '')
            },
            'currency_cell': 'B4'
        },
        'Monthly_Summary_Bills': {
            'title': {
                'A2': 'Bill.Billing_Month',
                'A3': 'Bill.Start_Time',
                'A4': 'Bill.End_Time',
                'A5': 'Bill.Create_Time',
                'A6': 'Bill.Total_Cost'
            },
            'value': {
                'B2': kwargs.get('bill_month', ''),
                'B3': kwargs.get('start_time', ''),
                'B4': kwargs.get('end_time', ''),
                'B5': kwargs.get('create_time', ''),
                'B6': kwargs.get('total', ''),
            },
            'currency_cell': 'B6'
        }
    }[bill_name]


"""
    Data structure description

    Head = [
        {
            "title": "Django.accounting.bill.User", # column name of table head
            "start_cell": "A6",  # The starting cell of the column name
            "end_cell": "A7"  # if different from start_cell, need to be merged
            "sub_cell": [
                {
                    "title": "Django.accounting.bill.GB*Day",
                    "start_cell": "E7",
                    "end_cell": "E7"
                },
                {
                    "title": "Django.accounting.bill.Cost",
                    "start_cell": "F7",
                    "end_cell": "F7"
                },
            ] # if exists, the means is table head contain sub cell
        }
    ]

    data_style = [
        {'A{row}': write_pure} # 'A{row}': it means cell of xlsx file
        {'B{row}': write_pure} # write_pure: it means style of cell
    ]

    end_style = [
        {
            'start_cell': 'A{row}',
            'end_cell': 'B{row}',
            'value': 'Django.accounting.bill.Sum_Total' # value of start_cell
        }
    ]
"""

# ------------------------CLUSTER-DAILY-REPORT-STYLE---------------------------


DEFAULT_GRES_DATA_STYLE = gres_data_style(DEFAULT_GRES_START_COL)
DEFAULT_GRES_DATA_LENTH = len(DEFAULT_GRES_DATA_STYLE)
DEFAULT_GRES_END_LINE = gres_end_line_style(DEFAULT_GRES_START_COL)
DEFAULT_GRES_END_LENTH = len(DEFAULT_GRES_END_LINE)

CLUSTER_DAILY_HEAD = {
    'cluster_daily_head': [
        {
            "title": "Django.accounting.bill.User",
            "start_cell": "A6",
            "end_cell": "A7"
        },
        {
            "title": "Django.accounting.bill.Billing_Group",
            "start_cell": "B6",
            "end_cell": "B7"
        },
        {
            "title": "Django.accounting.bill.Job_Number",
            "start_cell": "C6",
            "end_cell": "C7"
        },
        {
            "title": "Django.accounting.bill.Run_Time",
            "start_cell": "D6",
            "end_cell": "D7"
        },
        {
            "title": "Django.accounting.bill.Storage",
            "start_cell": "E6",
            "end_cell": "F6",
            "sub_cell": [
                {
                    "title": "Django.accounting.bill.GB*Day",
                    "start_cell": "E7",
                    "end_cell": "E7"
                },
                {
                    "title": "Django.accounting.bill.Cost",
                    "start_cell": "F7",
                    "end_cell": "F7"
                },
            ]
        },
        {
            "title": "Django.accounting.bill.CPU",
            "start_cell": "G6",
            "end_cell": "H6",
            "sub_cell": [
                {
                    "title": "Django.accounting.bill.Core*Hour",
                    "start_cell": "G7",
                    "end_cell": "G7"
                },
                {
                    "title": "Django.accounting.bill.Cost",
                    "start_cell": "H7",
                    "end_cell": "H7"
                },
            ]
        },
        {
            "title": "Django.accounting.bill.Memory",
            "start_cell": "I6",
            "end_cell": "J6",
            "sub_cell": [
                {
                    "title": "Django.accounting.bill.MB*Hour",
                    "start_cell": "I7",
                    "end_cell": "I7"
                },
                {
                    "title": "Django.accounting.bill.Cost",
                    "start_cell": "J7",
                    "end_cell": "J7"
                },
            ]
        }]+gres_head_dict(DEFAULT_GRES_START_COL, DEFAULT_HEAD_BEGIN_LINE-2)+[
        {
            "title": "Django.accounting.bill.Sum_Total",
            "start_cell": "{}{}".format(
                ascii_uppercase[DEFAULT_GRES_START_COL+len(GRES)*2],
                DEFAULT_HEAD_BEGIN_LINE-2),
            "end_cell": "{}{}".format(
                ascii_uppercase[DEFAULT_GRES_START_COL+len(GRES)*2],
                DEFAULT_HEAD_BEGIN_LINE-1)
        },
        {
            "title": "Django.accounting.bill.Discounted_Cost",
            "start_cell": "{}{}".format(
                ascii_uppercase[DEFAULT_GRES_START_COL+len(GRES)*2+1],
                DEFAULT_HEAD_BEGIN_LINE-2),
            "end_cell": "{}{}".format(
                ascii_uppercase[DEFAULT_GRES_START_COL+len(GRES)*2+1],
                DEFAULT_HEAD_BEGIN_LINE-1)
        }
    ],
    'title': 'Django.accounting.bill.Daily_Summary_Bills'
}

CLUSTER_DAILY_DATA_STYLE = [
                {'A{row}': write_pure},
                {'B{row}': write_pure},
                {'C{row}': write_right},
                {'D{row}': write_right_data},
                {'E{row}': write_right},
                {'F{row}': write_right_currency},
                {'G{row}': write_right_decimal},
                {'H{row}': write_right_currency},
                {'I{row}': write_right_decimal},
                {'J{row}': write_right_currency}]+DEFAULT_GRES_DATA_STYLE+[
                {'%s{row}' % (ascii_uppercase[
                    DEFAULT_GRES_DATA_LENTH+DEFAULT_GRES_START_COL]):
                    write_right_currency},
                {'%s{row}' % (ascii_uppercase[
                    DEFAULT_GRES_DATA_LENTH+DEFAULT_GRES_START_COL+1]):
                    write_right_currency},
            ]

CLUSTER_DAILY_END_LINE_DATA = [
    {
        'start_cell': 'A{row}',
        'end_cell': 'B{row}',
        'value': 'Django.accounting.bill.Sum_Total'
    },
    {
        'start_cell': 'C{row}',
        'end_cell': 'C{row}',
        'value': '=SUM(C{start_row}:C{end_row})'
    },
    {
        'start_cell': 'D{row}',
        'end_cell': 'D{row}',
        'value': '{total_runtime}'
    },
    {
        'start_cell': 'E{row}',
        'end_cell': 'E{row}',
        'value': '=SUM(E{start_row}:E{end_row})'
    },
    {
        'start_cell': 'F{row}',
        'end_cell': 'F{row}',
        'value': '=SUM(F{start_row}:F{end_row})'
    },
    {
        'start_cell': 'G{row}',
        'end_cell': 'G{row}',
        'value': '=SUM(G{start_row}:G{end_row})'
    },
    {
        'start_cell': 'H{row}',
        'end_cell': 'H{row}',
        'value': '=SUM(H{start_row}:H{end_row})'
    },
    {
        'start_cell': 'I{row}',
        'end_cell': 'I{row}',
        'value': '=SUM(I{start_row}:I{end_row})'
    },
    {
        'start_cell': 'J{row}',
        'end_cell': 'J{row}',
        'value': '=SUM(J{start_row}:J{end_row})'
    }]+DEFAULT_GRES_END_LINE+[
    {
        'start_cell': '%s{row}' % (
            ascii_uppercase[DEFAULT_GRES_END_LENTH+DEFAULT_GRES_START_COL]),
        'end_cell': '%s{row}' % (
            ascii_uppercase[DEFAULT_GRES_END_LENTH+DEFAULT_GRES_START_COL]),
        'value': '=SUM(%s{start_row}:%s{end_row})' % (
            ascii_uppercase[DEFAULT_GRES_END_LENTH+DEFAULT_GRES_START_COL],
            ascii_uppercase[DEFAULT_GRES_END_LENTH+DEFAULT_GRES_START_COL]
        )
    },
    {
        'start_cell': '%s{row}' % (
            ascii_uppercase[DEFAULT_GRES_END_LENTH+DEFAULT_GRES_START_COL+1]),
        'end_cell': '%s{row}' % (
            ascii_uppercase[DEFAULT_GRES_END_LENTH+DEFAULT_GRES_START_COL+1]),
        'value': '=SUM(%s{start_row}:%s{end_row})' % (
            ascii_uppercase[DEFAULT_GRES_END_LENTH+DEFAULT_GRES_START_COL+1],
            ascii_uppercase[DEFAULT_GRES_END_LENTH+DEFAULT_GRES_START_COL+1]
        )
    },
]

CLUSTER_DAILY_END_LINE_STYLE = \
    CLUSTER_DAILY_DATA_STYLE[:1] + CLUSTER_DAILY_DATA_STYLE[2:]

# ----------------------CLUSTER-MONTHLY-REPORT-STYLE---------------------------

CLUSTER_MONTHLY_HEAD = {
    'cluster_monthly_head': [
        {
            "title": "Django.accounting.bill.User",
            "start_cell": "A8",
            "end_cell": "A9"
        },
        {
            "title": "Django.accounting.bill.Job_Number",
            "start_cell": "B8",
            "end_cell": "B9"
        },
        {
            "title": "Django.accounting.bill.Run_Time",
            "start_cell": "C8",
            "end_cell": "C9"
        },
        {
            "title": "Django.accounting.bill.Storage",
            "start_cell": "D8",
            "end_cell": "E8",
            "sub_cell": [
                {
                    "title": "Django.accounting.bill.GB*Day",
                    "start_cell": "D9",
                    "end_cell": "D9"
                },
                {
                    "title": "Django.accounting.bill.Cost",
                    "start_cell": "E9",
                    "end_cell": "E9"
                },
            ]
        },
        {
            "title": "Django.accounting.bill.CPU",
            "start_cell": "F8",
            "end_cell": "G8",
            "sub_cell": [
                {
                    "title": "Django.accounting.bill.Core*Hour",
                    "start_cell": "F9",
                    "end_cell": "F9"
                },
                {
                    "title": "Django.accounting.bill.Cost",
                    "start_cell": "G9",
                    "end_cell": "G9"
                },
            ]
        },
        {
            "title": "Django.accounting.bill.Memory",
            "start_cell": "H8",
            "end_cell": "I8",
            "sub_cell": [
                {
                    "title": "Django.accounting.bill.MB*Hour",
                    "start_cell": "H9",
                    "end_cell": "H9"
                },
                {
                    "title": "Django.accounting.bill.Cost",
                    "start_cell": "I9",
                    "end_cell": "I9"
                },
            ]
        }]+gres_head_dict(CLUSTER_CRES_START_COL, DEFAULT_HEAD_BEGIN_LINE)+[
        {
            "title": "Django.accounting.bill.Sum_Total",
            "start_cell": "{}{}".format(
                ascii_uppercase[CLUSTER_CRES_START_COL+len(GRES)*2],
                DEFAULT_HEAD_BEGIN_LINE),
            "end_cell": "{}{}".format(
                ascii_uppercase[CLUSTER_CRES_START_COL+len(GRES)*2],
                DEFAULT_HEAD_BEGIN_LINE+1)
        },
        {
            "title": "Django.accounting.bill.Discounted_Cost",
            "start_cell": "{}{}".format(
                ascii_uppercase[CLUSTER_CRES_START_COL+len(GRES)*2+1],
                DEFAULT_HEAD_BEGIN_LINE),
            "end_cell": "{}{}".format(
                ascii_uppercase[CLUSTER_CRES_START_COL+len(GRES)*2+1],
                DEFAULT_HEAD_BEGIN_LINE+1)
        }
    ],
    'title': 'Django.accounting.bill.Monthly_Summary_Bills'
}

GRES_CLUSTER_MONTHLY_STYLE = gres_data_style(CLUSTER_CRES_START_COL)
GRES_CLUSTER_MONTHLY_LENTH = len(GRES_CLUSTER_MONTHLY_STYLE)
CLUSTER_MONTHLY_DATA_STYLE = [
                {'A{row}': write_pure},
                {'B{row}': write_right},
                {'C{row}': write_right_data},
                {'D{row}': write_right},
                {'E{row}': write_right_currency},
                {'F{row}': write_right_decimal},
                {'G{row}': write_right_currency},
                {'H{row}': write_right_decimal},
                {'I{row}': write_right_currency}]+GRES_CLUSTER_MONTHLY_STYLE+[
                {'%s{row}' % (ascii_uppercase[
                    GRES_CLUSTER_MONTHLY_LENTH+CLUSTER_CRES_START_COL]):
                    write_right_currency},
                {'%s{row}' % (ascii_uppercase[
                    GRES_CLUSTER_MONTHLY_LENTH+CLUSTER_CRES_START_COL+1]):
                    write_right_currency},
            ]

GRES_CLUSTER_MONTHLY_END_LINE = gres_end_line_style(CLUSTER_CRES_START_COL)
GRES_CLUSTER_MONTHLY_END_LENTH = len(GRES_CLUSTER_MONTHLY_END_LINE)
CLUSTER_MONTHLY_END_LINE_DATA = [
    {
        'start_cell': 'A{row}',
        'end_cell': 'A{row}',
        'value': 'Django.accounting.bill.Sum_Total'
    },
    {
        'start_cell': 'B{row}',
        'end_cell': 'B{row}',
        'value': '=SUM(B{start_row}:B{end_row})'
    },
    {
        'start_cell': 'C{row}',
        'end_cell': 'C{row}',
        'value': '{total_runtime}'
    },
    {
        'start_cell': 'D{row}',
        'end_cell': 'D{row}',
        'value': '=SUM(D{start_row}:D{end_row})'
    },
    {
        'start_cell': 'E{row}',
        'end_cell': 'E{row}',
        'value': '=SUM(E{start_row}:E{end_row})'
    },
    {
        'start_cell': 'F{row}',
        'end_cell': 'F{row}',
        'value': '=SUM(F{start_row}:F{end_row})'
    },
    {
        'start_cell': 'G{row}',
        'end_cell': 'G{row}',
        'value': '=SUM(G{start_row}:G{end_row})'
    },
    {
        'start_cell': 'H{row}',
        'end_cell': 'H{row}',
        'value': '=SUM(H{start_row}:H{end_row})'
    },
    {
        'start_cell': 'I{row}',
        'end_cell': 'I{row}',
        'value': '=SUM(I{start_row}:I{end_row})'
    }]+GRES_CLUSTER_MONTHLY_END_LINE+[
    {
        'start_cell': '%s{row}' % (ascii_uppercase[
            GRES_CLUSTER_MONTHLY_END_LENTH+CLUSTER_CRES_START_COL]),
        'end_cell': '%s{row}' % (ascii_uppercase[
            GRES_CLUSTER_MONTHLY_END_LENTH+CLUSTER_CRES_START_COL]),
        'value': '=SUM(%s{start_row}:%s{end_row})' % (
            ascii_uppercase[
                GRES_CLUSTER_MONTHLY_END_LENTH+CLUSTER_CRES_START_COL
            ],
            ascii_uppercase[
                GRES_CLUSTER_MONTHLY_END_LENTH+CLUSTER_CRES_START_COL
            ]
        )
    },
    {
        'start_cell': '%s{row}' % (ascii_uppercase[
            GRES_CLUSTER_MONTHLY_END_LENTH+CLUSTER_CRES_START_COL+1]),
        'end_cell': '%s{row}' % (ascii_uppercase[
            GRES_CLUSTER_MONTHLY_END_LENTH+CLUSTER_CRES_START_COL+1]),
        'value': '=SUM(%s{start_row}:%s{end_row})' % (
            ascii_uppercase[
                GRES_CLUSTER_MONTHLY_END_LENTH+CLUSTER_CRES_START_COL+1],
            ascii_uppercase[
                GRES_CLUSTER_MONTHLY_END_LENTH+CLUSTER_CRES_START_COL+1]
        )
    },
]

# ------------------------USER-MONTHLY-REPORT-STYLE----------------------------

USER_MONTHLY_HEAD = {
    'user_monthly_head': [
        {
            "title": "Django.accounting.bill.Date",
            "start_cell": "A8",
            "end_cell": "A9"
        },
        {
            "title": "Django.accounting.bill.Billing_Group",
            "start_cell": "B8",
            "end_cell": "B9"
        },
        {
            "title": "Django.accounting.bill.Job_Number",
            "start_cell": "C8",
            "end_cell": "C9"
        },
        {
            "title": "Django.accounting.bill.Run_Time",
            "start_cell": "D8",
            "end_cell": "D9"
        },
        {
            "title": "Django.accounting.bill.Storage",
            "start_cell": "E8",
            "end_cell": "F8",
            "sub_cell": [
                {
                    "title": "Django.accounting.bill.GB*Day",
                    "start_cell": "E9",
                    "end_cell": "E9"
                },
                {
                    "title": "Django.accounting.bill.Cost",
                    "start_cell": "F9",
                    "end_cell": "F9"
                },
            ]
        },
        {
            "title": "Django.accounting.bill.CPU",
            "start_cell": "G8",
            "end_cell": "H8",
            "sub_cell": [
                {
                    "title": "Django.accounting.bill.Core*Hour",
                    "start_cell": "G9",
                    "end_cell": "G9"
                },
                {
                    "title": "Django.accounting.bill.Cost",
                    "start_cell": "H9",
                    "end_cell": "H9"
                },
            ]
        },
        {
            "title": "Django.accounting.bill.Memory",
            "start_cell": "I8",
            "end_cell": "J8",
            "sub_cell": [
                {
                    "title": "Django.accounting.bill.MB*Hour",
                    "start_cell": "I9",
                    "end_cell": "I9"
                },
                {
                    "title": "Django.accounting.bill.Cost",
                    "start_cell": "J9",
                    "end_cell": "J9"
                },
            ]
        }]+gres_head_dict(DEFAULT_GRES_START_COL, 8)+[
        {
            "title": "Django.accounting.bill.Sum_Total",
            "start_cell": "{}{}".format(
                ascii_uppercase[DEFAULT_GRES_START_COL+len(GRES)*2], 8),
            "end_cell": "{}{}".format(
                ascii_uppercase[DEFAULT_GRES_START_COL+len(GRES)*2], 9)
        },
        {
            "title": "Django.accounting.bill.Discounted_Cost",
            "start_cell": "{}{}".format(
                ascii_uppercase[DEFAULT_GRES_START_COL+len(GRES)*2+1], 8),
            "end_cell": "{}{}".format(
                ascii_uppercase[DEFAULT_GRES_START_COL+len(GRES)*2+1], 9)
        }],
    'title': 'Django.accounting.bill.User_Monthly_Bills'
}

USER_MONTHLY_DATA_STYLE = \
    [
        {'A{row}': write_pure},
        {'B{row}': write_pure},
        {'C{row}': write_right},
        {'D{row}': write_right_data},
        {'E{row}': write_right},
        {'F{row}': write_right_currency},
        {'G{row}': write_right_decimal},
        {'H{row}': write_right_currency},
        {'I{row}': write_right_decimal},
        {'J{row}': write_right_currency}]+DEFAULT_GRES_DATA_STYLE+[
        {'%s{row}' % (
            ascii_uppercase[DEFAULT_GRES_DATA_LENTH+DEFAULT_GRES_START_COL]):
            write_right_currency},
        {'%s{row}' % (
            ascii_uppercase[DEFAULT_GRES_DATA_LENTH+DEFAULT_GRES_START_COL+1]):
            write_right_currency}
    ]

USER_MONTHLY_END_LINE_DATA = [
    {
        'start_cell': 'A{row}',
        'end_cell': 'B{row}',
        'value': 'Django.accounting.bill.Sum_Total'
    },
    {
        'start_cell': 'C{row}',
        'end_cell': 'C{row}',
        'value': '=SUM(C{start_row}:C{end_row})'
    },
    {
        'start_cell': 'D{row}',
        'end_cell': 'D{row}',
        'value': '{total_runtime}'
    },
    {
        'start_cell': 'E{row}',
        'end_cell': 'E{row}',
        'value': '=SUM(E{start_row}:E{end_row})'
    },
    {
        'start_cell': 'F{row}',
        'end_cell': 'F{row}',
        'value': '=SUM(F{start_row}:F{end_row})'
    },
    {
        'start_cell': 'G{row}',
        'end_cell': 'G{row}',
        'value': '=SUM(G{start_row}:G{end_row})'
    },
    {
        'start_cell': 'H{row}',
        'end_cell': 'H{row}',
        'value': '=SUM(H{start_row}:H{end_row})'
    },
    {
        'start_cell': 'I{row}',
        'end_cell': 'I{row}',
        'value': '=SUM(I{start_row}:I{end_row})'
    },
    {
        'start_cell': 'J{row}',
        'end_cell': 'J{row}',
        'value': '=SUM(J{start_row}:J{end_row})'
    }]+DEFAULT_GRES_END_LINE+[
    {
        'start_cell': '%s{row}' % (
            ascii_uppercase[DEFAULT_GRES_END_LENTH+DEFAULT_GRES_START_COL]),
        'end_cell': '%s{row}' % (
            ascii_uppercase[DEFAULT_GRES_END_LENTH+DEFAULT_GRES_START_COL]),
        'value': '=SUM(%s{start_row}:%s{end_row})' % (
            ascii_uppercase[DEFAULT_GRES_END_LENTH+DEFAULT_GRES_START_COL],
            ascii_uppercase[DEFAULT_GRES_END_LENTH+DEFAULT_GRES_START_COL]
        )
    },
    {
        'start_cell': '%s{row}' % (
            ascii_uppercase[DEFAULT_GRES_END_LENTH+DEFAULT_GRES_START_COL+1]),
        'end_cell': '%s{row}' % (
            ascii_uppercase[DEFAULT_GRES_END_LENTH+DEFAULT_GRES_START_COL+1]),
        'value': '=SUM(%s{start_row}:%s{end_row})' % (
            ascii_uppercase[DEFAULT_GRES_END_LENTH+DEFAULT_GRES_START_COL+1],
            ascii_uppercase[DEFAULT_GRES_END_LENTH+DEFAULT_GRES_START_COL+1]
        )
    },
]
USER_MONTHLY_END_LINE_STYLE = \
    USER_MONTHLY_DATA_STYLE[:1] + USER_MONTHLY_DATA_STYLE[2:]

# ------------------------USER-DAILY-REPORT-STYLE-----------------------------


def user_daily_report_head(s_len):
    return {
        "storage_head": [
            {
                "title": "Django.accounting.bill.Storage",
                "start_cell": "A8",
                "end_cell": "C9"
            },
            {
                "title": "Django.accounting.bill.Storage_Quota(GB)",
                "start_cell": "D8",
                "end_cell": "D9"
            },
            {
                "title": "Django.accounting.bill.Storage",
                "start_cell": "E8",
                "end_cell": "G8",
                "sub_cell": [
                    {
                        "title": "Django.accounting.bill.GB*Day",
                        "start_cell": "E9",
                        "end_cell": "E9"
                    },
                    {
                        "title": "Django.accounting.bill.Used",
                        "start_cell": "F9",
                        "end_cell": "F9"
                    },
                    {
                        "title": "Django.accounting.bill.Cost",
                        "start_cell": "G9",
                        "end_cell": "G9"
                    }
                ]
            },
            {
                "title": "Django.accounting.bill.Sum_Total",
                "start_cell": "H8",
                "end_cell": "H9"
            },
            {
                "title": "Django.accounting.bill.Discount",
                "start_cell": "I8",
                "end_cell": "I9"
            },
            {
                "title": "Django.accounting.bill.Discounted_Cost",
                "start_cell": "J8",
                "end_cell": "J9"
            }
        ],
        "job_head": [
            {
                "title": "Django.accounting.bill.Record_ID",
                "start_cell": "A{0}".format(14+s_len),
                "end_cell": "A{0}".format(15+s_len)
            },
            {
                "title": "Django.accounting.bill.Job_ID_Name",
                "start_cell": "B{0}".format(14+s_len),
                "end_cell": "B{0}".format(15+s_len)
            },
            {
                "title": "Django.accounting.bill.Queue",
                "start_cell": "C{0}".format(14+s_len),
                "end_cell": "C{0}".format(15+s_len)
            },
            {
                "title": "Django.accounting.bill.Run_Time",
                "start_cell": "D{0}".format(14+s_len),
                "end_cell": "D{0}".format(15+s_len)
            },
            {
                "title": "Django.accounting.bill.CPU",
                "start_cell": "E{0}".format(14+s_len),
                "end_cell": "G{0}".format(14+s_len),
                "sub_cell": [
                    {
                        "title": "Django.accounting.bill.Core*Hour",
                        "start_cell": "E{0}".format(15+s_len),
                        "end_cell": "E{0}".format(15+s_len)
                    },
                    {
                        "title": "Django.accounting.bill.Used",
                        "start_cell": "F{0}".format(15+s_len),
                        "end_cell": "F{0}".format(15+s_len)
                    },
                    {
                        "title": "Django.accounting.bill.Cost",
                        "start_cell": "G{0}".format(15+s_len),
                        "end_cell": "G{0}".format(15+s_len)
                    }
                ]
            },
            {
                "title": "Django.accounting.bill.Memory",
                "start_cell": "H{0}".format(14+s_len),
                "end_cell": "J{0}".format(14+s_len),
                "sub_cell": [
                    {
                        "title": "Django.accounting.bill.MB*Hour",
                        "start_cell": "H{0}".format(15+s_len),
                        "end_cell": "H{0}".format(15+s_len)
                    },
                    {
                        "title": "Django.accounting.bill.Used",
                        "start_cell": "I{0}".format(15+s_len),
                        "end_cell": "I{0}".format(15+s_len)
                    },
                    {
                        "title": "Django.accounting.bill.Cost",
                        "start_cell": "J{0}".format(15+s_len),
                        "end_cell": "J{0}".format(15+s_len)
                    }
                ]
            },
        ]+gres_head_dict(
            DEFAULT_GRES_START_COL, 14+s_len, user_daily_type=True) +
        [
            {
                "title": "Django.accounting.bill.Sum_Total",
                "start_cell": "{}{}".format(
                    ascii_uppercase[
                        DEFAULT_GRES_START_COL+len(GRES)*3], 14+s_len),
                "end_cell": "{}{}".format(
                    ascii_uppercase[
                        DEFAULT_GRES_START_COL+len(GRES)*3], 15+s_len)
            },
            {
                "title": "Django.accounting.bill.Discount",
                "start_cell": "{}{}".format(
                    ascii_uppercase[
                        DEFAULT_GRES_START_COL+len(GRES)*3+1], 14+s_len
                ),
                "end_cell": "{}{}".format(
                    ascii_uppercase[
                        DEFAULT_GRES_START_COL+len(GRES)*3+1], 15+s_len
                )
            },
            {
                "title": "Django.accounting.bill.Discounted_Cost",
                "start_cell": "{}{}".format(
                    ascii_uppercase[
                        DEFAULT_GRES_START_COL+len(GRES)*3+2], 14+s_len
                ),
                "end_cell": "{}{}".format(
                    ascii_uppercase[
                        DEFAULT_GRES_START_COL+len(GRES)*3+2], 15+s_len
                )
            }
        ],
        "title": "Django.accounting.bill.User_Daily_Bills"
    }


GRES_USER_DAILY_STYLE = list()
for col in range(0, len(GRES)*3, 3):
    GRES_USER_DAILY_STYLE.extend(
        [{'%s{row}' % (ascii_uppercase[10+col]): write_right},
         {'%s{row}' % (ascii_uppercase[11+col]): write_right},
         {'%s{row}' % (ascii_uppercase[12+col]): write_right_currency}]
    )

# Conversion of resource units by title of key value
RESOURCE_UNIT = {
            'Django.accounting.bill.CPU': 'Django.accounting.bill.Core',
            'Django.accounting.bill.Memory': 'Django.accounting.bill.MB',
            'Django.accounting.bill.Storage': 'Django.accounting.bill.GB',
        }

USER_DAILY_STORAGE_DATA_STYLE = [
                {'A{row}': write_pure},
                {'D{row}': write_right},
                {'E{row}': write_right},
                {'F{row}': write_right},
                {'G{row}': write_right_currency},
                {'H{row}': write_right_currency},
                {'I{row}': write_right},
                {'J{row}': write_right_currency},
            ]


USER_DAILY_JOB_DATA_STYLE = [
                {'A{row}': write_pure},
                {'B{row}': write_pure},
                {'C{row}': write_pure},
                {'D{row}': write_right_data},
                {'E{row}': write_right},
                {'F{row}': write_right},
                {'G{row}': write_right_currency},
                {'H{row}': write_right},
                {'I{row}': write_right},
                {'J{row}': write_right_currency}]+GRES_USER_DAILY_STYLE+[
                {'%s{row}' % (ascii_uppercase[
                    len(GRES_USER_DAILY_STYLE)+DEFAULT_GRES_START_COL]):
                    write_right_currency},
                {'%s{row}' % (ascii_uppercase[len(
                    GRES_USER_DAILY_STYLE)+DEFAULT_GRES_START_COL+1]):
                    write_right},
                {'%s{row}' % (ascii_uppercase[
                    len(GRES_USER_DAILY_STYLE)+DEFAULT_GRES_START_COL+2]):
                    write_right_currency},
            ]


GRES_USER_DAILY_END_LIEN = list()
for col in range(0, len(GRES)*3, 3):
    GRES_USER_DAILY_END_LIEN.extend([
        {'start_cell': '%s{row}' % (
            ascii_uppercase[DEFAULT_GRES_START_COL+col]),
         'end_cell': '%s{row}' % (
             ascii_uppercase[DEFAULT_GRES_START_COL+col]),
         'value': '/'},
        {'start_cell': '%s{row}' % (
            ascii_uppercase[DEFAULT_GRES_START_COL+col+1]),
         'end_cell': '%s{row}' % (
             ascii_uppercase[DEFAULT_GRES_START_COL+col+1]),
         'value': '/'},
        {'start_cell': '%s{row}' % (
            ascii_uppercase[DEFAULT_GRES_START_COL+col+2]),
         'end_cell': '%s{row}' % (
             ascii_uppercase[DEFAULT_GRES_START_COL+col+2]),
         'value': '=SUM(%s{start_row}:%s{end_row})' % (
             ascii_uppercase[DEFAULT_GRES_START_COL+col+2],
             ascii_uppercase[DEFAULT_GRES_START_COL+col+2])}
    ])
GRES_DAILY_END_LENTH = len(GRES_USER_DAILY_END_LIEN)

USER_DAILY_END_LINE_DATA = {
        'storage_end': [
            {
                'start_cell': 'A{row}',
                'end_cell': 'C{row}',
                'value': 'Django.accounting.bill.Sum_Total'
            },
            {
                'start_cell': 'D{row}',
                'end_cell': 'D{row}',
                'value': '=SUM(D{start_row}:D{end_row})'
            },
            {
                'start_cell': 'E{row}',
                'end_cell': 'E{row}',
                'value': '/'
            },
            {
                'start_cell': 'F{row}',
                'end_cell': 'F{row}',
                'value': '=SUM(F{start_row}:F{end_row})'
            },
            {
                'start_cell': 'G{row}',
                'end_cell': 'G{row}',
                'value': '=SUM(G{start_row}:G{end_row})'
            },
            {
                'start_cell': 'H{row}',
                'end_cell': 'H{row}',
                'value': '=SUM(H{start_row}:H{end_row})'
            },
            {
                'start_cell': 'I{row}',
                'end_cell': 'I{row}',
                'value': '/'
            },
            {
                'start_cell': 'J{row}',
                'end_cell': 'J{row}',
                'value': '=SUM(J{start_row}:J{end_row})'
            }
        ],
        'job_end': [
            {
                'start_cell': 'A{row}',
                'end_cell': 'C{row}',
                'value': 'Django.accounting.bill.Sum_Total'
            },
            {
                'start_cell': 'D{row}',
                'end_cell': 'D{row}',
                'value': '{total_runtime}'
            },
            {
                'start_cell': 'E{row}',
                'end_cell': 'E{row}',
                'value': '/'
            },
            {
                'start_cell': 'F{row}',
                'end_cell': 'F{row}',
                'value': '/'
            },
            {
                'start_cell': 'G{row}',
                'end_cell': 'G{row}',
                'value': '=SUM(G{start_row}:G{end_row})'
            },
            {
                'start_cell': 'H{row}',
                'end_cell': 'H{row}',
                'value': '/'
            },
            {
                'start_cell': 'I{row}',
                'end_cell': 'I{row}',
                'value': '/'
            },
            {
                'start_cell': 'J{row}',
                'end_cell': 'J{row}',
                'value': '=SUM(J{start_row}:J{end_row})'
            }
        ]+GRES_USER_DAILY_END_LIEN+[
            {
                'start_cell': '%s{row}' % (
                    ascii_uppercase[
                        GRES_DAILY_END_LENTH+DEFAULT_GRES_START_COL]),
                'end_cell': '%s{row}' % (
                    ascii_uppercase[
                        GRES_DAILY_END_LENTH+DEFAULT_GRES_START_COL]),
                'value': '=SUM(%s{start_row}:%s{end_row})' % (
                    ascii_uppercase[
                        GRES_DAILY_END_LENTH+DEFAULT_GRES_START_COL],
                    ascii_uppercase[
                        GRES_DAILY_END_LENTH+DEFAULT_GRES_START_COL])
            },
            {
                'start_cell': '%s{row}' % (
                    ascii_uppercase[
                        GRES_DAILY_END_LENTH+DEFAULT_GRES_START_COL+1]),
                'end_cell': '%s{row}' % (
                    ascii_uppercase[
                        GRES_DAILY_END_LENTH+DEFAULT_GRES_START_COL+1]),
                'value': '/'
            },
            {
                'start_cell': '%s{row}' % (
                    ascii_uppercase[
                        GRES_DAILY_END_LENTH+DEFAULT_GRES_START_COL+2]),
                'end_cell': '%s{row}' % (
                    ascii_uppercase[
                        GRES_DAILY_END_LENTH+DEFAULT_GRES_START_COL+2]),
                'value': '=SUM(%s{start_row}:%s{end_row})' % (
                    ascii_uppercase[
                        GRES_DAILY_END_LENTH+DEFAULT_GRES_START_COL+2],
                    ascii_uppercase[
                        GRES_DAILY_END_LENTH+DEFAULT_GRES_START_COL+2])
            }
        ]
    }

USER_DAILY_END_LINE_STYLE = \
    USER_DAILY_JOB_DATA_STYLE[:1] + USER_DAILY_JOB_DATA_STYLE[3:]
