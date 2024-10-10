# urls.py
#
# Copyright (c) 2024 Daniel Andrlik
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

from django.urls import path

from podcast_analyzer import views

app_name = "podcast_analyzer"

urlpatterns = [
    path("", view=views.PodcastListView.as_view(), name="podcast-list"),
    path("add/", view=views.PodcastCreateView.as_view(), name="podcast-create"),
    path(
        "<uuid:id>/",
        view=views.PodcastDetailView.as_view(),
        name="podcast-detail",
    ),
    path(
        "<uuid:id>/edit/",
        view=views.PodcastUpdateView.as_view(),
        name="podcast-edit",
    ),
    path(
        "<uuid:id>/delete/",
        view=views.PodcastDeleteView.as_view(),
        name="podcast-delete",
    ),
]
