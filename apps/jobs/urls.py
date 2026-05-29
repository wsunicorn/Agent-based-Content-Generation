"""URL patterns for the jobs app."""
from django.urls import path

from . import views

app_name = "jobs"

urlpatterns = [
    path("", views.job_list_create, name="list-create"),
    path("<uuid:pk>/", views.job_detail, name="detail"),
    path("<uuid:pk>/cancel/", views.job_cancel, name="cancel"),
    path("<uuid:pk>/evidence/", views.job_evidence, name="evidence"),
    path("<uuid:pk>/outline/approve/", views.job_approve_outline, name="approve-outline"),
    path("<uuid:pk>/sections/<int:section_id>/regenerate/", views.job_regenerate_section, name="regenerate-section"),
    path("<uuid:pk>/export/", views.job_export, name="export"),
    path("<uuid:pk>/content/", views.job_update_content, name="update-content"),
    path("<uuid:pk>/artifacts/<str:artifact_type>/", views.job_artifact, name="artifact"),
]
