# Copyright 2015-present Lenovo
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
import subprocess  # nosec B404
import tempfile

from pkg_resources import Requirement, working_set

from lico.core.contrib.client import Client


def create_policy(policy_dict, client):
    exist_policy = [policy['name']
                    for policy in client.get_list_retention_policies()]
    for policy in policy_dict.keys():
        policy_type = 'create' if policy not in exist_policy else 'alter'
        policy_func = getattr(client, policy_type + '_retention_policy')
        policy_func(**policy_dict[policy])


def drop_all_measurements(client):
    measurements = ['cluster_metric', 'gpu_metric', 'job_monitor_metric',
                    'mig_metric', 'node_metric',
                    'nodegroup_metric', 'rack_metric']

    for measurement in measurements:
        client.drop_measurement(measurement)


def upgrade_database(client, settings):
    from lico.core.base._version import version_tuple

    lico_version = '_'.join([str(e) for e in version_tuple[:3]])
    databases = client.get_list_database()
    measurements = client.get_list_measurements()
    names = [database['name'] for database in databases]
    backup_database = f"lico_backup_for_{lico_version}_upgrade"

    if backup_database not in names and \
            client._database in names and measurements:
        with tempfile.TemporaryDirectory() as tmpdir:
            if backup_to_tmp(client, tmpdir, settings):
                restore_to_backup_db(client._database, backup_database, tmpdir)
        drop_all_measurements(client)


def backup_to_tmp(client, tmpdir, settings):
    backup_command = [
        'influxd', 'backup', '-portable', '-db', client._database,
        '-host', f'{client._host}:'
                 f'{settings.MONITOR.INFLUX.get("rpc_port", 8088)}',
        tmpdir
    ]
    try:
        completed_process = subprocess.run(  # nosec B603
            backup_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True
        )
        if b'backup complete' in completed_process.stdout:
            return True
        else:
            return False
    except subprocess.CalledProcessError as e:
        raise Exception(f'backup_influxdb: {e.stderr}')
    except OSError as e:
        raise Exception(f'backup_influxdb: {e.strerror}')


def restore_to_backup_db(from_db, to_db, tmpdir):
    restore_command = [
        'influxd', 'restore', '-portable', '-db', from_db,
        '-newdb', to_db, tmpdir
    ]

    try:
        subprocess.run(  # nosec B603
            restore_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True
        )
    except subprocess.CalledProcessError as e:
        raise Exception(f'restore: {e.stderr}')
    except OSError as e:
        raise Exception(f'restore: {e.strerror}')
    except Exception as err:
        raise err


def on_init(self, settings):
    policy_dict = {
        'hour': {
            'name': 'hour',
            'duration': '6h',
            'replication': '1',
            'default': True,
        },
        'day': {
            'name': 'day',
            'duration': '1d',
            'replication': '1',
        },
        'week': {
            'name': 'week',
            'duration': '7d',
            'replication': '1',
        },
        'month': {

            'name': 'month',
            'duration': '31d',
            'replication': '1',
        },
    }

    client = Client().influxdb_client()

    upgrade_database(client, settings)

    client.create_database(client._database)

    # if excute "lico init" again,
    # create retention policy or modify existed retention policy
    create_policy(policy_dict, client)

    # if excute "lico init" again, delete existed continuous queries
    exist_continuous_query = ['day_summary', 'week_summary',
                              'month_summary',
                              'str_day_summary', 'str_week_summary',
                              'str_month_summary']
    for query_name in exist_continuous_query:
        client.drop_continuous_query(query_name)

    day_select = \
        'SELECT last(value) as value ' \
        'INTO "day".:MEASUREMENT ' \
        'FROM "hour".nodegroup_metric ' \
        'GROUP BY time(12m),* '
    client.create_continuous_query(
        name='day_summary',
        select=day_select,
    )
    week_select = \
        'SELECT last(value) as value ' \
        'INTO "week".:MEASUREMENT ' \
        'FROM "day".nodegroup_metric ' \
        'GROUP BY time(1h24m),* '
    client.create_continuous_query(
        name='week_summary',
        select=week_select,
    )
    month_select = \
        'SELECT last(value) as value ' \
        'INTO "month".:MEASUREMENT ' \
        'FROM "week".nodegroup_metric ' \
        'GROUP BY time(6h12m),* '
    client.create_continuous_query(
        name='month_summary',
        select=month_select,
    )

    # node_metric/gpu_metric value type is string,
    # it is necessary to create query polices separately
    str_day_select = \
        'SELECT last(value) as value ' \
        'INTO "day".:MEASUREMENT ' \
        'FROM "hour"./(node|gpu|gpu_logical_dev)_metric/ ' \
        'GROUP BY time(12m),* '
    client.create_continuous_query(
        name='str_day_summary',
        select=str_day_select,
    )
    str_week_select = \
        'SELECT last(value) as value ' \
        'INTO "week".:MEASUREMENT ' \
        'FROM "day"./(node|gpu|gpu_logical_dev)_metric/ ' \
        'GROUP BY time(1h24m),* '
    client.create_continuous_query(
        name='str_week_summary',
        select=str_week_select,
    )
    str_month_select = \
        'SELECT last(value) as value ' \
        'INTO "month".:MEASUREMENT ' \
        'FROM "week"./(node|gpu|gpu_logical_dev)_metric/ ' \
        'GROUP BY time(6h12m),* '
    client.create_continuous_query(
        name='str_month_summary',
        select=str_month_select,
    )


def on_config_scheduler(self, scheduler, settings):
    from .tasks import (
        cluster_res_summaries, group_summaries, summaries, sync_vnc,
    )
    tasks_dict = {
        cluster_res_summaries: '*/15',
        summaries: '*/15',
        group_summaries: '*/15',
        sync_vnc: '*/30'
    }

    scheduler.add_executor(
        'processpool', alias=self.name, max_workers=len(tasks_dict)
    )

    for task, cron_time in tasks_dict.items():
        scheduler.add_job(
            func=task,
            trigger='cron',
            second=cron_time,
            max_instances=1,
            executor=self.name,
        )

    if working_set.find(Requirement('lico-core-vgpu')) is not None:
        from .tasks import sync_vgpu_parent_uuid
        scheduler.add_job(
            func=sync_vgpu_parent_uuid,
            trigger='cron',
            second='*/30',
            max_instances=1,
            executor=self.name,
        )
