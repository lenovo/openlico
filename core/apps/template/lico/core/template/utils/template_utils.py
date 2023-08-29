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

import hashlib
import logging
import uuid
from collections import defaultdict

import pkg_resources
from django.conf import settings
from django.template import Template

from lico.core.container.exceptions import ImageFileNotExist
from lico.core.container.singularity.models import SingularityImage

from ..exceptions import (
    ImportChecksumException, ImportSchedulerException, ImportVersionException,
    IntelTensorFlowImageNotExist, JupyterImageNotExist,
    JupyterLabImageNotExist, RstudioImageNotExist, TemplateRenderException,
)

logger = logging.getLogger(__name__)


def template_render(user, template_content, param_vals):
    try:
        lico = LicoParameter(user)
        script = Template(template_content).render(
            generate_context(param_vals, lico)
        )
        return script
    except JupyterImageNotExist as e:
        raise e
    except JupyterLabImageNotExist as e:
        raise e
    except IntelTensorFlowImageNotExist as e:
        raise e
    except RstudioImageNotExist as e:
        raise e
    except SingularityImage.DoesNotExist:
        raise ImageFileNotExist
    except Exception as e:
        logger.exception("The job template rendering error.")
        raise TemplateRenderException(str(e)) from e


def generate_context(param_vals, lico):
    from django.template.context import Context

    return Context(
        DefaultDict(
            lambda: None,
            lico=lico,
            **param_vals
        ), autoescape=False
    )


class LicoParameter(object):
    def __init__(self, user):
        self.user = user
        # self.context = user.context

    def __getattr__(self, key):
        import re

        # Support all csres codes not only port
        # Support single and multi allocating
        # lico.port0 or lico.port12 means single allocating
        # lico.port0_2 or lico.port_0_3_5 means multi allocating
        # lico.port0_2 is range allocating
        # lico.port_0_3_5 is seperate allocating
        csres_single_ret = re.match(r'^.+(\d+)$', key)
        csres_multi_range_ret = re.match(r'^.+(\d+)_(\d+)$', key)
        csres_multi_seperate_ret = re.match(r'^.+_(.+)$', key)
        if csres_single_ret is None \
                and csres_multi_range_ret is None \
                and csres_multi_seperate_ret is None:
            raise AttributeError(
                "{} object has no attribute {}".format('LicoParameter', key)
            )

        return "@@{lico_" + key + "}"


class DefaultDict(defaultdict):
    def __contains__(self, item):
        # used for django template
        return True


export_key = ['version', 'MagicNumber', 'exporter', 'export_time',
              'source', 'scheduler', 'index', 'name', 'category', 'logo',
              'desc', 'parameters_json', 'template_file']


def md5value(s):
    md5 = hashlib.md5()  # nosec B324
    md5.update(s.encode("utf-8"))
    return md5.hexdigest()


def export_template_file(data):
    text = ''
    separator = '=' * 30 + data.get('MagicNumber') + '=' * 30 + "\n"
    exist_separator = False
    for key in export_key:

        line_content = str(data.get(key)) + '\n'
        if key in ['desc', 'parameters_json', 'template_file']:
            if exist_separator:
                line_content = line_content + separator
            else:
                line_content = separator + line_content + separator
            exist_separator = True

        text += line_content

    Checksum = 'LICO' + text + 'LICO'
    text += md5value(Checksum)
    return text


def import_template_file(job_file):
    """
    :param job_file:
5.4.0
70281590-dda8-11e9-8513-000c298778ab
lico
1569205111
LRZ
slurm
test
data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD
==============================70281590-dda8-11e9-8513-000c298778ab==============================
test
==============================70281590-dda8-11e9-8513-000c298778ab==============================
[{"dataType": "string", "name": "Job Name", \
"input": "input", "maxLength": 32, "id": "job_name", \
"must": true, "type": "system", "class": "base"}, \
{"dataType": "folder", "name": "Workspace", "id": "job_workspace", \
"must": true, "type": "system", "class": "param"}]
==============================70281590-dda8-11e9-8513-000c298778ab==============================
apiVersion:batch/v1
==============================70281590-dda8-11e9-8513-000c298778ab==============================
f6d0e1a3568baca6144a3e71cff79249
    """
    import_dict = {
        'desc': '',
        'parameters_json': '',
        'template_file': '',
        'Checksum': ''
    }
    import_key = export_key + ['Checksum']
    cont_list = job_file.readlines()
    i = 0
    mark = False
    read_check = ''
    magic_line = '=' * 30 + \
                 cont_list[1].splitlines()[0].decode(encoding="utf-8") + \
                 '=' * 30 + '\n'
    total_line = int(len(cont_list))
    for index, curr_line in enumerate(cont_list):

        modify_line = curr_line.decode(encoding="utf-8").replace('\r\n', '\n')
        if index != total_line - 1:
            read_check += modify_line
        if modify_line == magic_line:
            i += 0 if mark is False else 1
            mark = True
            continue
        if import_key[i] not in ['desc', 'parameters_json', 'template_file']:
            import_dict[import_key[i]] = modify_line.splitlines()[0]
            i += 1
        else:
            import_dict[import_key[i]] += modify_line
    for key in ['desc', 'parameters_json', 'template_file']:
        import_dict[key] = import_dict[key][0: -1]
    check_importdict(import_dict, read_check)
    return import_dict


def check_importdict(import_dict, read_check):
    # Compare version
    if import_dict['version'] != pkg_resources.\
            get_distribution('lico-core-template').version and\
            import_dict['version'].split(".")[0] != '5':
        logger.error('version not supported')
        raise ImportVersionException

    # check uuid
    if not isinstance(uuid.UUID(import_dict['MagicNumber']), uuid.UUID):
        logger.error('UUID is error')
        raise ImportChecksumException

    # check scheduler
    if import_dict['scheduler'] != settings.LICO.SCHEDULER:
        logger.error('The scheduler type  is not supported')
        raise ImportSchedulerException

    # check checksum
    check_sum = md5value('LICO' + read_check + 'LICO')
    logger.info(import_dict['Checksum'])
    if check_sum != import_dict['Checksum']:
        logger.error('check_sum is error')
        raise ImportChecksumException
