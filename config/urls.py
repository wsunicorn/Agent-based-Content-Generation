"""URL configuration for content_pipeline project."""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from apps.jobs.views import analytics_summary, health_check

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/jobs/", include("apps.jobs.urls")),
    path("api/analytics/", analytics_summary, name="analytics"),
    path("api/health/", health_check, name="health"),
    path("", include("apps.dashboard.urls")),
]

if settings.DEBUG:
    import debug_toolbar
    urlpatterns += [path("__debug__/", include(debug_toolbar.urls))]
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += staticfiles_urlpatterns()
