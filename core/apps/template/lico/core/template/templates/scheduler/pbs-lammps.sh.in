#!/bin/bash
#PBS -N {{ job_name }}
#PBS -q {{ job_queue }}
#PBS -j oe
{% get_now as current %}#PBS -o {{ job_workspace }}/{{ job_name }}-{{ current }}.out
{% if gpu_per_node %}
#PBS -l select={{ nodes|default:1 }}{% if not exclusive|default_if_none:True %}:ncpus={{ cores_per_node|default:1 }}{% endif %}{% if ram_size %}:mem={{ ram_size }}mb{% endif %}{% if gpu_per_node or use_gpu %}:ngpus={{ gpu_per_node|default:1 }}{% endif %}
#PBS -l place=scatter
{% else %}
#PBS -l select={{ cores_per_node|default:1 }}:ncpus=1:mpiprocs=1{% if ram_size %}:mem={{ ram_size }}mb{% endif %}
{% endif %}
{% if run_time %}#PBS -l walltime={% format_pbs_walltime run_time %}{% endif %}
#PBS -V
cd {{ job_workspace }}

ENV_JOB_ID=${PBS_JOBID%%.*}
