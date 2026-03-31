"""URL patterns for the jobs app."""
from django.urls import path

from . import views

app_name = "jobs"

urlpatterns = [
    path("", views.job_list_create, name="list-create"),
    path("<uuid:pk>/", views.job_detail, name="detail"),
    path("<uuid:pk>/cancel/", views.job_cancel, name="cancel"),
    path("<uuid:pk>/export/", views.job_export, name="export"),
    path("<uuid:pk>/content/", views.job_update_content, name="update-content"),
    path("<uuid:pk>/artifacts/<str:artifact_type>/", views.job_artifact, name="artifact"),
]
