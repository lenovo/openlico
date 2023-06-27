from rest_framework.response import Response

from lico.core.contrib.authentication import RemoteJWTInternalAuthentication
from lico.core.contrib.views import InternalAPIView

from ..models import Job


class JobList(InternalAPIView):
    authentication_classes = (
        RemoteJWTInternalAuthentication,
    )

    def post(self, request):
        field_list = [
            "id",
            "submitter",
            "job_running",
            "job_name",
            "state",
            "operate_state",
            "tres",
            "end_time",
        ]
        job_id_list = request.data.get("job_id_list", [])
        submitter = request.data.get("submitter", "")
        query = Job.objects.filter(delete_flag=False, submitter=submitter,
                                   id__in=job_id_list)
        job_list = query.as_dict(include=field_list)
        return Response(job_list)
