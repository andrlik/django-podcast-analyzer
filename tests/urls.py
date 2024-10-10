# urls.py
#
# Copyright (c) 2024 Daniel Andrlik
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Root url conf for testing."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include, path
from django.views import defaults as default_views

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path(
        "400/",
        default_views.bad_request,
        kwargs={"exception": Exception("Bad Request!")},
    ),
    path(
        "403/",
        default_views.permission_denied,
        kwargs={"exception": Exception("Permission Denied!")},
    ),
    path(
        "404/",
        default_views.page_not_found,
        kwargs={"exception": Exception("Not Found!")},
    ),
    path(
        "500/",
        default_views.server_error,
        kwargs={"exception": Exception("Server Error!")},
    ),
    path("podcasts/", include("podcast_analyzer.urls", namespace="podcast_analyzer")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

urlpatterns += staticfiles_urlpatterns()
