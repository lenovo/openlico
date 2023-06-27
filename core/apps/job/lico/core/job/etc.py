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


jobs_detail_host_head = [
    "job.Job ID", "job.Job Name", "job.Status", "job.Queue", "job.Submit Time",
    "job.Start Time", "job.End Time", "job.Submitter", "job.CPU Core Num",
    "job.CPU Core Time (Core*s)", "job.GPU Num", "job.GPU Time (Card*s)"]
user_detail_host_head = ["job.Submitter",
                         ["job.Job ID", "job.Job Name", "job.Status",
                          "job.Queue", "job.Submit Time", "job.Start Time",
                          "job.End Time", "job.Submitter", "job.CPU Core Num",
                          "job.CPU Core Time (Core*s)",
                          "job.GPU Num", "job.GPU Time (Card*s)"]]
I18N = {
    "user_statistics": {
        "head": [
            "job.User Name",
            [
                "job.Submit Date",
                "job.User Name",
                "job.Job Num",
                "job.CPU Core Num",
                "job.CPU Core Time (Core*s)",
                "job.GPU Num",
                "job.GPU Time (Card*s)"
            ]
        ],
        "title": "job.User Job Statistics Report"
    },
    "bill_details": {
        "head": [
            "job.Billing Group Name",
            [
                "job.Job ID",
                "job.Job Name",
                "job.Status",
                "job.Queue",
                "job.Submit Time",
                "job.Start Time",
                "job.End Time",
                "job.Submitter",
                "job.CPU Core Num",
                "job.CPU Core Time (Core*s)",
                "job.GPU Num",
                "job.GPU Time (Card*s)"
            ]
        ],
        "title": "job.BillingGroup Job Detailed Report"
    },
    "jobs_statistics": {
        "head": [
            "job.Submit Date",
            "job.Job Num",
            "job.CPU Core Num",
            "job.CPU Core Time (Core*s)",
            "job.GPU Num",
            "job.GPU Time (Card*s)"
        ],
        "title": "job.Job Statistics Report"
    },
    "user_details": {
        "head": user_detail_host_head,
        "title": "job.User Job Detailed Report"
    },
    "jobs_details": {
        "head": jobs_detail_host_head,
        "title": "job.Job Detailed Report"
    },
    "bill_statistics": {
        "head": [
            "job.Billing Group Name",
            [
                "job.Submit Date",
                "job.Billing Group Name",
                "job.Job Num",
                "job.CPU Core Num",
                "job.CPU Core Time (Core*s)",
                "job.GPU Num",
                "job.GPU Time (Card*s)"
            ]
        ],
        "title": "job.BillingGroup Job Statistics Report"
    }
}
