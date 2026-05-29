"""Dashboard views — minimal HTML interface."""
from functools import wraps

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from apps.jobs.models import Job


def login_required_in_production(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if settings.DEBUG:
            return view_func(request, *args, **kwargs)
        return login_required(view_func)(request, *args, **kwargs)

    return wrapped


@login_required_in_production
def index(request):
    return render(request, "dashboard/index.html")


@login_required_in_production
def job_detail_page(request, pk):
    """Full-page article viewer for a single completed job."""
    job = get_object_or_404(Job, pk=pk)
    return render(request, "dashboard/job_detail.html", {"job": job})
