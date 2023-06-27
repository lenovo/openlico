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

from django import template

register = template.Library()


@register.simple_tag
def format_lsf_walltime(runtime):
    # Runtime format follows Slurm
    # eg. 3d 4h 12m
    vals = runtime.split(' ')
    if len(vals) >= 1 and len(vals) <= 3:
        total_minutes = 0
        for val in vals:
            num_str = val[:-1]
            unit = val[-1].lower()
            if num_str.isdigit():
                num = int(num_str)
                if unit == 'd':
                    total_minutes += num * 24 * 60
                elif unit == 'h':
                    total_minutes += num * 60
                elif unit == 'm':
                    total_minutes += num
                else:
                    return '24:00'
            else:
                return '24:00'
        total_hours = int(total_minutes / 60)
        minutes = total_minutes % 60
        return str(total_hours) + ':' + str(minutes)
    else:
        return '24:00'
