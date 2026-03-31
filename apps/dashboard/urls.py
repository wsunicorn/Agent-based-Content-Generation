"""URL patterns for the dashboard app."""
from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.index, name="index"),
    path("jobs/<uuid:pk>/", views.job_detail_page, name="job-detail"),
]
