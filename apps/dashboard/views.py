"""Dashboard views — minimal HTML interface."""
from django.shortcuts import get_object_or_404, render

from apps.jobs.models import Job


def index(request):
    return render(request, "dashboard/index.html")


def job_detail_page(request, pk):
    """Full-page article viewer for a single completed job."""
    job = get_object_or_404(Job, pk=pk)
    return render(request, "dashboard/job_detail.html", {"job": job})
