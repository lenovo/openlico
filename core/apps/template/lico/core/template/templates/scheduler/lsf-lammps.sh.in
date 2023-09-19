#!/bin/bash
#BSUB -J {{ job_name }}
#BSUB -q {{ job_queue }}
#BSUB -cwd {{ job_workspace }}
{% get_now as current %}#BSUB -o {{ job_name }}-{{ current }}.out
#BSUB -e {{ job_name }}-{{ current }}.out

{% if ram_size %}
#BSUB -R "rusage[mem={{ ram_size }}M]"
{% endif %}

{% if gpu_per_node or use_gpu %}
#BSUB -n {{ nodes|default:1|multi:cores_per_node|default:1 }}
#BSUB -R "span[ptile={{ cores_per_node|default:1 }}]{% if ram_size %} rusage[mem={{ ram_size }}M]{% endif %}"
#BSUB -gpu "num={{ gpu_per_node|default:1 }}{% if gpu_resource_name %}:mig={{ gpu_resource_name }}{% endif %}:j_exclusive=yes"
{% else %}
#BSUB -n {{ nodes|default:1|multi:cores|default:1 }}
{% endif %}
{% if run_time %}#BSUB -W {% format_lsf_walltime run_time %}{% endif %}

ENV_JOB_ID=$LSB_JOBID


